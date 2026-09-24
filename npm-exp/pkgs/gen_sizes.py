import os, sys
import pandas as pd
from pathlib import Path
from pathlib import PosixPath

EXTENSIONS = {
    'npm': '.tgz',
    'xz': '.tar.xz',
    'brotli': '.tar.br',
    'zstd': '.tar.zst',
    'zopfli': '.tgz'
}

def return_dir_files(ext: str) -> list[str]:
    '''
    Returns all the files from a specified @dirpath 
    and collects all the files with the expected extension. 
    '''
    target_extension = EXTENSIONS[ext]

    dirpath = Path(ext)
    if not dirpath.is_dir():
        raise FileNotFoundError(f"directory {dirpath} not found")
    # collects files with expected extension
    return [
        filepath for filepath in dirpath.iterdir()
        if filepath.is_file() and filepath.name.endswith(target_extension)
    ]


def get_sizes(files : list[Path]) -> list[dict]:
    return [
        {'name': f, 'size' : f.stat().st_size} for f in files
    ]

def true_stem(p: Path) -> str:
    name = os.path.basename(str(p))
    for ext in list(EXTENSIONS.values()):
        if name.endswith(ext):
            return name[: -len(ext)]
    return p.stem


if __name__ == '__main__':
    try:
        arg = sys.argv[1] 
        dirname = sys.argv[2]
        extension = EXTENSIONS.get(arg)

    except IndexError:
        print(f"Usage: {sys.argv[0]} <algorithm> <output-path>")
        print(f"Example: {sys.argv[0]} npm foo")
        sys.exit(1)

    if extension is None:
        raise KeyError(f"no extension configured for {arg}") 

    paths = return_dir_files(arg)
    packages = get_sizes(paths)

    for p in packages:
        p['key'] = true_stem(p['name'])

    pd.DataFrame(packages).to_csv(f'{dirname}/{arg}.csv', index=False)
