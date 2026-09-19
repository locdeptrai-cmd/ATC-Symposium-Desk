Gold VHF ATC corpus (on-prem). Do not commit WAV.

Layout:

  data/asr-gold/dataset_v1/manifest.jsonl
  data/asr-gold/dataset_v1/wav/<utterance_id>.wav
  data/asr-gold/source/<logger-filename>   optional copies of full files

Export HUMAN corrections only:

  python tools/asr_dataset/export_gold.py --audio-root D:\logger\SGN

Eval baseline (corrections table, no GPU):

  python tools/asr_eval.py --from-corrections
