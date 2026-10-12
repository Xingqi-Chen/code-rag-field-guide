"""Download only inference assets; never execute repository-provided model code."""
import os
os.environ.setdefault('HF_HOME', '.cache/huggingface')
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
from huggingface_hub import snapshot_download
snapshot_download('sentence-transformers/all-MiniLM-L6-v2',
 revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
 local_dir='.cache/model', allow_patterns=['*.json','*.txt','model.safetensors','1_Pooling/*'],
 ignore_patterns=['onnx/*','openvino/*'])
print('Model assets downloaded; revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41')
