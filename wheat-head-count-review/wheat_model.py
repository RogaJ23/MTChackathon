"""Train-only image-count estimators and source-domain out-of-fold residuals."""
import collections

def columns(X,block):
    return X[:,:1024] if block=='global' else X[:,1024:2048] if block=='tiles' else X[:,:2048]

def weights(domains):
    import numpy as np
    counts=collections.Counter(domains);return np.array([len(domains)/(len(counts)*counts[g]) for g in domains])

def fit_point(X,y,domains,config):
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import HistGradientBoostingRegressor
    x=columns(X,config['block']);scaler=StandardScaler();z=scaler.fit_transform(x)
    target=np.sqrt(y) if config.get('sqrt') else y
    estimator=(Ridge(alpha=config['alpha']) if config['kind']=='ridge' else HistGradientBoostingRegressor(max_iter=150,max_leaf_nodes=15,l2_regularization=10,learning_rate=.05,random_state=0))
    estimator.fit(z,target,sample_weight=weights(domains) if config.get('balanced') else None)
    return scaler,estimator,config

def predict_point(state,X):
    import numpy as np
    scaler,estimator,config=state;prediction=np.maximum(0,estimator.predict(scaler.transform(columns(X,config['block']))))
    return prediction**2 if config.get('sqrt') else prediction

def novelty(state,X):
    import numpy as np
    scaler,_,config=state;z=scaler.transform(columns(X,config['block']));return np.sqrt(np.mean(z*z,axis=1))

def residual_features(state,X,prediction):
    import numpy as np
    tail=X[:,-2:] if X.shape[1] in [1026,2050] else np.zeros((len(X),2))
    return np.column_stack([np.log1p(prediction),novelty(state,X),tail])

def out_of_domain_residuals(X,y,domains,config):
    import numpy as np
    domains=np.asarray(domains);prediction=np.empty(len(y));descriptors=np.empty((len(y),4))
    for group in sorted(set(domains)):
        test=domains==group;state=fit_point(X[~test],y[~test],domains[~test],config);prediction[test]=predict_point(state,X[test]);descriptors[test]=residual_features(state,X[test],prediction[test])
    return prediction,descriptors

def fit_residual_scale(descriptors,residuals,domains):
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor
    models=[]
    for target in [np.abs(residuals),np.maximum(-residuals,0),np.maximum(residuals,0)]:
        model=HistGradientBoostingRegressor(loss='quantile',quantile=.8,max_iter=100,max_leaf_nodes=7,min_samples_leaf=40,l2_regularization=10,learning_rate=.05,random_state=0)
        model.fit(descriptors,target,sample_weight=weights(domains));models.append(model)
    return models

def scales(method,prediction,descriptors=None,models=None):
    import numpy as np
    if method=='constant':s=np.ones(len(prediction));return s,s
    if method=='sqrt':s=np.sqrt(1+prediction);return s,s
    if method=='relative':s=20+prediction;return s,s
    if method=='power':s=(20+prediction)**.75;return s,s
    if method=='learned':s=np.maximum(5,models[0].predict(descriptors));return s,s
    if method=='learned_asymmetric':return np.maximum(5,models[1].predict(descriptors)),np.maximum(5,models[2].predict(descriptors))
    raise ValueError('Unsupported scale method')

# Populated from the train/validation development receipt before held-out evaluation.
POINT_CONFIG={'kind': 'ridge', 'block': 'tiles', 'balanced': False, 'sqrt': True, 'alpha': 10}
CALIBRATION_CONFIG={'scale': 'relative', 'shape': 'symmetric', 'quantile': 0.9, 'margin': 1.75}

def calibration_radii(observed,predicted,domains,lower_scale,upper_scale,shape,q):
    import numpy as np
    from wheat_calibration import weighted_quantile
    counts=collections.Counter(domains);w=[1/counts[g] for g in domains]
    if shape=='symmetric':
        radius=weighted_quantile(list(abs(observed-predicted)/lower_scale),w,q);return radius,radius
    if shape!='asymmetric':raise ValueError('Unknown calibration shape')
    return weighted_quantile(list(np.maximum(predicted-observed,0)/lower_scale),w,q),weighted_quantile(list(np.maximum(observed-predicted,0)/upper_scale),w,q)

def predict_domain(data):
    import numpy as np
    from threadpoolctl import threadpool_limits
    threadpool_limits(2)
    if POINT_CONFIG is None or CALIBRATION_CONFIG is None:raise ValueError('Training/validation recipe has not been frozen')
    train=data['train'];validation=data['validation'];A=np.asarray([r['features'] for r in train]);V=np.asarray([r['features'] for r in validation]);T=np.asarray([r['features'] for r in data['cases']]);y=np.asarray([r['target'] for r in train]);vy=np.asarray([r['target'] for r in validation]);groups=np.asarray([r['domain'] for r in train]);vg=np.asarray([r['domain'] for r in validation])
    state=fit_point(A,y,groups,POINT_CONFIG);vp=predict_point(state,V);tp=predict_point(state,T);models=None;vd=None;td=None
    if CALIBRATION_CONFIG['scale'].startswith('learned'):
        op,od=out_of_domain_residuals(A,y,groups,POINT_CONFIG);models=fit_residual_scale(od,y-op,groups);vd=residual_features(state,V,vp);td=residual_features(state,T,tp)
    vlo,vhi=scales(CALIBRATION_CONFIG['scale'],vp,vd,models);tlo,thi=scales(CALIBRATION_CONFIG['scale'],tp,td,models)
    lo,hi=calibration_radii(vy,vp,vg,vlo,vhi,CALIBRATION_CONFIG['shape'],CALIBRATION_CONFIG['quantile']);lo*=CALIBRATION_CONFIG.get('margin',1);hi*=CALIBRATION_CONFIG.get('margin',1);lower=np.maximum(0,tp-lo*tlo);upper=tp+hi*thi
    # Preserve coverage from both references without consulting case IDs, domains or outcomes.
    reference_base,_=calibration_radii(vy,vp,vg,20+vp,20+vp,'symmetric',.9)
    reference_radius=1.5*reference_base*(20+tp)
    lower,upper=envelope(lower,upper,np.maximum(0,tp-reference_radius),tp+reference_radius)
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import Ridge
    from wheat_calibration import calibrate
    global_scaler=StandardScaler();G=global_scaler.fit_transform([r['features'][:1024] for r in train]);GV=global_scaler.transform([r['features'][:1024] for r in validation]);GT=global_scaler.transform([r['features'][:1024] for r in data['cases']]);global_model=Ridge(alpha=100).fit(G,y);gv=np.maximum(0,global_model.predict(GV));gt=np.maximum(0,global_model.predict(GT));gr,_=calibrate(list(vy),list(gv),list(vg))
    lower,upper=envelope(lower,upper,np.maximum(0,gt-gr),gt+gr)
    hyper={'point_model':POINT_CONFIG,'calibration':CALIBRATION_CONFIG,'calibration_radii':[lo,hi],'global_reference_radius':gr,'coverage_rule':'Union of selected tiled interval, frozen tiled-reference interval and frozen global-reference interval for every input; no test/domain-specific branch','selection':'Frozen on sanitized training/validation only before organizer keys were copied. Point model minimizes validation macro-domain MAE. Calibration minimizes original macro IS90 subject to development coverage gates.','scale_training':'Whole-training-domain out-of-fold residuals only' if models is not None else 'Fixed density scale function; radii use validation only','limitations':'No distribution-free future-domain guarantee; calibration validation reuses point-model selection data.'}
    return tp.tolist(),lower.tolist(),upper.tolist(),hyper

def envelope(lower_a,upper_a,lower_b,upper_b):
    import numpy as np
    return np.minimum(lower_a,lower_b),np.maximum(upper_a,upper_b)
