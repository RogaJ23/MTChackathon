"""Retrieve one image by source/row after verifying its entire pinned Parquet. Never export labels."""
import argparse,hashlib,io,json,pathlib,urllib.request,gzip

def retrieve(row,manifest,output):
    import pyarrow as pa
    import pyarrow.parquet as pq
    item=next(x for x in manifest if pathlib.Path(x['file']).name==row['source_file']);buffer=io.BytesIO();digest=hashlib.sha256();size=0
    with urllib.request.urlopen(item['url'],timeout=90) as response:
        while chunk:=response.read(4*1024*1024):size+=len(chunk);digest.update(chunk);buffer.write(chunk)
    if digest.hexdigest()!=item['sha256'] or size!=item['bytes']:raise ValueError('Source identity changed')
    buffer.seek(0);index=0
    for batch in pq.ParquetFile(pa.BufferReader(buffer.getvalue())).iter_batches(batch_size=16,columns=['image']):
        for value in batch.column('image').to_pylist():
            if index==row['source_row']:
                raw=value['bytes'];h=hashlib.sha256(raw).hexdigest()
                if h!=row['image_sha256']:raise ValueError('Image identity mismatch')
                output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(raw);return {'id':row['id'],'source_bytes':size,'source_sha256':digest.hexdigest(),'image_sha256':h,'image_bytes':len(raw),'raw_parquet_persisted':False,'label_columns_read':False}
            index+=1
    raise ValueError('Source row missing')

def main():
    import sys
    sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
    from data_io import load_data
    ap=argparse.ArgumentParser();ap.add_argument('--id',required=True);ap.add_argument('--output',type=pathlib.Path,required=True);args=ap.parse_args();q=pathlib.Path(__file__).resolve().parent/'07-wheat';data=json.loads(gzip.decompress((q/'data.json.gz').read_bytes()));row=next(r for r in data['cases'] if r['id']==args.id);print(json.dumps(retrieve(row,json.loads((q/'retrieval.json').read_text()),args.output),indent=2))
if __name__=='__main__':main()
