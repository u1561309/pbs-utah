"""Reproduce descriptive EDA from raw exports or reuse validated cleaning output."""
from pathlib import Path
import argparse
import json

from analysis.donor_eda import run_donor_eda, plot_donor_eda
from analysis.extended_eda import run_extended_eda, plot_extended_eda


def reproduce(root, cleaned_run=None):
    root = Path(root).resolve()
    if Path.cwd().resolve() != root:
        raise ValueError('Run this command from the project root.')
    if cleaned_run is None:
        notebook_path = root / 'analysis.ipynb'
        if not notebook_path.exists():
            notebook_path = root / 'notebooks' / 'analysis.ipynb'
        notebook = json.loads(notebook_path.read_text())
        by_id = {cell['id']: cell for cell in notebook['cells']}
        clean_cells = ['pbs-utah-02', 'pbs-clean-24', 'pbs-clean-26', 'pbs-clean-28',
                       'pbs-clean-30', 'pbs-clean-32', 'pbs-clean-readback']
        namespace = {}
        for cell_id in clean_cells:
            cell = by_id[cell_id]
            exec(compile(''.join(cell['source']), f'analysis.ipynb:{cell_id}', 'exec'), namespace)
        cleaned_run = namespace['OUT']
        del namespace
    else:
        cleaned_run = Path(cleaned_run).resolve()
    donor = run_donor_eda(root, cleaned_run)
    plot_donor_eda(donor)
    extended = run_extended_eda(root, cleaned_run, donor['output'])
    plot_extended_eda(extended)
    result = {'cleaned_run': str(cleaned_run), 'donor_run': str(donor['output']),
              'extended_eda_run': str(extended['output'])}
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cleaned-run', help='Validated cleaning directory; omit to clean original exports.')
    args = parser.parse_args()
    reproduce(Path.cwd(), args.cleaned_run)
