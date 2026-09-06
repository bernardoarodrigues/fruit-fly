"""Read metadata for the complete inventoried APL ABF set, without voltage data."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pyabf

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / 'validation/apl-sk-ephys-inventory.json'
OUT = ROOT / 'validation/apl-sk-abf-headers.json'


def main():
    if OUT.exists(): raise FileExistsError('Preserve completed header inventory')
    inventory = json.loads(INVENTORY.read_text())
    sources = [r for r in inventory['entries'] if r['member'].endswith('.abf') and 'extracted_path' in r]
    records = []
    for row in sources:
        path = ROOT / row['extracted_path']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError(f'Source mismatch: {path}')
        abf = pyabf.ABF(str(path), loadData=False)
        public_keys = ('abfID','abfVersionString','creator','abfDateTimeString','holdingCommand',
                       'protocolPath','protocol','abfFileComment','nOperationMode',
                       'userList','userListEnable','userListParamToVary','userListRepeat',
                       'dataPointCount','channelCount','dataRate','sweepCount','adcNames',
                       'adcUnits','dacNames','dacUnits','sweepPointCount','sweepLengthSec',
                       'sweepIntervalSec','tagComments','tagTimesSec')
        metadata = {k:getattr(abf,k) for k in public_keys}
        sections = {}
        for key in ('_protocolSection','_adcSection','_dacSection','_epochPerDacSection','_epochSection'):
            section = getattr(abf,key,None)
            if section is not None:
                sections[key] = {k:v for k,v in vars(section).items() if not k.startswith('_')}
        records.append(dict(member=row['member'],sha256=row['sha256'],extracted_path=row['extracted_path'],
                            candidate_recording_directory=row['candidate_recording_directory'],
                            metadata=metadata,raw_header_sections=sections))
    result = dict(completed_utc=datetime.now(timezone.utc).isoformat(),pyabf_version=pyabf.__version__,
        pyabf_documentation='https://swharden.com/pyabf/',
        inventory_sha256=hashlib.sha256(INVENTORY.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        expected_files=len(sources),parsed_files=len(records),
        sample_rates=dict(Counter(str(r['metadata']['dataRate']) for r in records)),
        channel_units=dict(Counter(str(r['metadata']['adcUnits']) for r in records)),
        protocols=dict(Counter(r['metadata']['protocol'] for r in records)),
        creators=dict(Counter(r['metadata']['creator'] for r in records)),
        scope='All extracted APL ABF headers only, loadData=False. No voltage measurements or cohort fitting. DAC epoch tables are commanded waveforms, not independently measured injected current. Header offsets and telegraph fields do not alone prove biological liquid-junction or bridge corrections.',
        records=records)
    OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))


if __name__ == '__main__': main()
