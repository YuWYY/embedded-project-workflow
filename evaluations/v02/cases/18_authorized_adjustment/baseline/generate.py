from pathlib import Path
import json
p=Path(__file__).resolve().parent
c=json.loads((p/'config.json').read_text())
assert 8 <= c['queue_capacity'] <= 32
(p/'generated.h').write_text('#define QUEUE_CAPACITY '+str(c['queue_capacity'])+'\n')
