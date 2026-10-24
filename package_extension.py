"""Package an unpaired Connector build for public distribution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED

UPSTREAM = '876e41ad15139077f2e07b2f71a0fa94742e0b4a'
PRIVATE = {'.bridge-token', 'mcp-private-config.json', '.env'}
PATTERNS = [r'[A-Za-z]:[/\\]Users[/\\][^/\\\s]+',
            r'gh[pousr]_[A-Za-z0-9]{20,}', r'github_pat_[A-Za-z0-9_]{20,}',
            r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----']


def package(source, output, version):
    source = Path(source).resolve()
    output = Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError('Keep release output outside the extension directory')
    manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('name') != 'Zotero Connector (MCP Bridge)' or manifest.get('manifest_version') != 3:
        raise ValueError('Expected an MV3 MCP Bridge build')
    root = Path(__file__).resolve().parent
    if not (source/'background.js').read_text(encoding='utf-8').rstrip().endswith(
            (root/'bridge-background.js').read_text(encoding='utf-8').rstrip()):
        raise ValueError('Build bridge code differs from the published source')
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Use a three-part numeric release version')
    files = []
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if path.name in PRIVATE:
            continue
        if any(part.startswith('.') for part in relative.parts) or path.suffix in {'.log','.sqlite','.pdf'}:
            raise ValueError('Unexpected runtime/data file in build: '+relative.as_posix())
        data = path.read_bytes()
        if path.suffix in {'.js','.json','.html','.css','.txt','.md','.map'}:
            if any(re.search(pattern,data.decode('utf-8',errors='replace')) for pattern in PATTERNS):
                raise ValueError('Private data signature in: '+relative.as_posix())
        files.append((relative.as_posix(), data))
    manifest['version_name'] = f'MCP Bridge {version} (Connector {manifest["version"]})'
    output.mkdir(parents=True,exist_ok=True)
    archive = output/f'zotero-connector-bridge-{version}.zip'
    with ZipFile(archive,'x',ZIP_DEFLATED) as zipfile:
        for name,data in files:
            zipfile.writestr(name,json.dumps(manifest,ensure_ascii=False,indent=2).encode()
                             if name=='manifest.json' else data)
        zipfile.writestr('INSTALL.txt',
            'Extract this archive to connector-ready inside the matching MCP source directory.\n'
            'Run: python prepare.py provision --output connector-ready\n'
            'This generates private local pairing automatically; do not share the paired folder.\n'
            'Load connector-ready as an unpacked extension, then start the MCP service.\n'
            'No bridge tab or manual token entry is required.\n')
        zipfile.writestr('SOURCE.md',
            f'# Corresponding source\n\nBridge release: {version}\n\n'
            f'https://github.com/belvme/zotero-connector-mcp/tree/v{version}\n\n'
            f'Official Connector source: https://github.com/zotero/zotero-connectors/tree/{UPSTREAM}\n\n'
            'Initialize the upstream submodules at their pinned revisions and follow the repository build instructions.\n'
            'Bridge modifications and build scripts are in the bridge release source.\n'
            'Keep COPYING and upstream/submodule license notices with redistributed builds.\n')
    with ZipFile(archive) as zipfile:
        assert zipfile.testzip() is None
        assert not any(Path(name).name in PRIVATE for name in zipfile.namelist())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/'SHA256SUMS.txt').write_text(checksum+'  '+archive.name+'\n',encoding='utf-8')
    return {'archive':archive.name,'bytes':archive.stat().st_size,'sha256':checksum,
            'private_pairing':'excluded','files':len(files)+2}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('connector-ready'))
    parser.add_argument('--output',type=Path,default=Path('dist'))
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    print(json.dumps(package(args.source,args.output,args.version)))
