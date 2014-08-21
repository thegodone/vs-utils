"""
Featurize molecules and save features to disk. Featurizers are exposed as
subcommands, with __init__ arguments as subcommand arguments.
"""

__author__ = "Steven Kearnes"
__copyright__ = "Copyright 2014, Stanford University"
__license__ = "BSD 3-clause"

import argparse
import cPickle
import gzip
import inspect
import joblib

from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit_utils import serial

from pande_gas.features import get_featurizers
from pande_gas.utils.parallel_utils import LocalCluster


def parse_args(input_args=None):
    """
    Parse command-line arguments. Each featurizer class is a subcommand
    whose arguments are stored in args.featurizer_kwargs. The featurizer
    class is stored in args.klass.

    Parameters
    ----------
    input_args : list, optional
        Input arguments. If not provided, defaults to sys.argv[1:].
    """
    parser = argparse.ArgumentParser(formatter_class=HelpFormatter)
    parser.add_argument('input',
                        help='Input molecules.')
    parser.add_argument('--chiral-scaffolds', action='store_true',
                        help='Whether to include chirality in scaffolds.')
    parser.add_argument('-t', '--targets',
                        help='Molecule targets.')
    parser.add_argument('-p', '--parallel', action='store_true',
                        help='Whether to use IPython.parallel.')
    parser.add_argument('-id', '--cluster-id',
                        help='IPython.parallel cluster ID.')
    parser.add_argument('-np', '--n-engines', type=int,
                        help='Start a local IPython.parallel cluster with ' +
                             'this many engines.')
    parser.add_argument('output',
                        help='Output filename (.joblib, .pkl, or .pkl.gz).')
    parser.add_argument('-c', '--compression-level', type=int, default=3,
                        help='Compression level (0-9) to use with ' +
                             'joblib.dump.')

    # featurizer subcommands
    featurizers = get_featurizers()
    subparsers = parser.add_subparsers(title='featurizers')
    for name, klass in featurizers.items():
        command = subparsers.add_parser(name, help=klass.__doc__,
                                        formatter_class=HelpFormatter,
                                        epilog=klass.__doc__)
        command.set_defaults(klass=klass)
        try:
            args, _, _, defaults = inspect.getargspec(klass.__init__)
        except TypeError:
            args = []
        for i, arg in enumerate(args):
            if i == 0 and arg == 'self':
                continue
            kwargs = {}
            try:
                kwargs['default'] = defaults[i-len(args)]
                if kwargs['default'] is not None:
                    kwargs['type'] = type(kwargs['default'])
            except IndexError:
                kwargs['required'] = True
            if 'type' in kwargs and kwargs['type'] == bool:
                if kwargs['default']:
                    command.add_argument('--no-{}'.format(arg), dest=arg,
                                         action='store_false')
                else:
                    command.add_argument('--{}'.format(arg),
                                         action='store_true')
            else:
                command.add_argument('--{}'.format(arg), **kwargs)
    args = argparse.Namespace()
    args.featurizer_kwargs = parser.parse_args(input_args)
    for arg in ['input', 'output', 'klass', 'targets', 'parallel',
                'cluster_id', 'n_engines', 'compression_level',
                'chiral_scaffolds']:
        setattr(args, arg, getattr(args.featurizer_kwargs, arg))
        delattr(args.featurizer_kwargs, arg)
    return args


class HelpFormatter(argparse.RawTextHelpFormatter):
    """
    Argparse help formatter with better indenting.

    Parameters
    ----------
    WRITEME
    """
    def __init__(self, prog, indent_increment=2, max_help_position=8,
                 width=None):
        super(HelpFormatter, self).__init__(prog, indent_increment,
                                            max_help_position, width)


def main(featurizer_class, input_filename, output_filename,
         target_filename=None, featurizer_kwargs=None, parallel=False,
         client_kwargs=None, view_flags=None, compression_level=3,
         chiral_scaffolds=False):
    """
    Featurize molecules in input_filename using the given featurizer.

    Parameters
    ----------
    featurizer_class : Featurizer
        Featurizer class.
    input_filename : str
        Filename containing molecules to be featurized.
    output_filename : str
        Output filename. Should end with .pkl or .pkl.gz.
    targets : array_like, optional
        Molecule target values.
    featurizer_kwargs : dict, optional
        Keyword arguments passed to featurizer.
    parallel : bool, optional
        Whether to train subtrainers in parallel using IPython.parallel
        (default False).
    client_kwargs : dict, optional
        Keyword arguments for IPython.parallel Client.
    view_flags : dict, optional
        Flags for IPython.parallel LoadBalancedView.
    compression_level : int, optional (default 3)
        Compression level (0-9) to use with joblib.dump.
    chiral_scaffods : bool, optional (default False)
        Whether to include chirality in scaffolds.
    """
    mols, names, scaffolds = read_mols(input_filename, chiral_scaffolds)

    # featurize molecules
    if featurizer_kwargs is None:
        featurizer_kwargs = {}
    featurizer = featurizer_class(**featurizer_kwargs)
    features = featurizer.featurize(mols, parallel, client_kwargs, view_flags)

    # build data container
    data = {'features': features, 'names': names, 'scaffolds': scaffolds}
    if target_filename is not None:
        with open(target_filename) as f:
            targets = cPickle.load(f)
        assert len(targets) == len(mols)
        data['y'] = targets
    data['args'] = {'featurizer_class': featurizer_class.__name__,
                    'input_filename': input_filename,
                    'target_filename': target_filename,
                    'featurizer_kwargs': featurizer_kwargs,
                    'chiral_scaffolds': chiral_scaffolds}

    # write output file
    write_output_file(data, output_filename, compression_level)


def read_mols(input_filename, chiral_scaffolds=False):
    """
    Read molecules from an input file and extract names and scaffolds.

    Parameters
    ----------
    input_filename : str
        Filename containing molecules.
    chiral_scaffods : bool, optional (default False)
        Whether to include chirality in scaffolds.
    """
    reader = serial.MolReader()
    reader.open(input_filename)
    mols = []
    names = []
    scaffolds = []
    for mol in reader.get_mols():
        mols.append(mol)
        if mol.HasProp('_Name'):
            names.append(mol.GetProp('_Name'))
        else:
            raise ValueError('Molecule names are required.')
        scaffolds.append(MurckoScaffold.MurckoScaffoldSmiles(
            mol=mol, includeChirality=chiral_scaffolds))
    reader.close()
    return mols, names, scaffolds


def write_output_file(data, output_filename, compression_level=3):
    """
    Pickle output data, possibly to a compressed file.

    Parameters
    ----------
    data : object
        Object to pickle in output file.
    output_filename : str
        Output filename. Should end with .joblib, .pkl, or .pkl.gz.
    compression_level : int, optional (default 3)
        Compression level (0-9) to use with joblib.dump.
    """
    if output_filename.endswith('.pkl'):
        with open(output_filename, 'wb') as f:
            cPickle.dump(data, f, cPickle.HIGHEST_PROTOCOL)
    elif output_filename.endswith('.pkl.gz'):
        with gzip.open(output_filename, 'wb') as f:
            cPickle.dump(data, f, cPickle.HIGHEST_PROTOCOL)
    elif output_filename.endswith('.joblib'):
        joblib.dump(data, output_filename, compress=compression_level)
    else:
        raise NotImplementedError('Unrecognized output file extension.')

if __name__ == '__main__':
    args = parse_args()

    # start a cluster
    if args.n_engines is not None:
        assert args.cluster_id is None, ('Cluster ID should not be should ' +
                                         'not be specified when starting a' +
                                         'new cluster.')
        cluster = LocalCluster(args.n_engines)
        args.parallel = True
        args.cluster_id = cluster.cluster_id

    # cluster flags
    if args.cluster_id is not None:
        client_kwargs = {'cluster_id': args.cluster_id}
    else:
        client_kwargs = None
    view_flags = {'retries': 1}

    # run main function
    main(args.klass, args.input, args.output, args.targets,
         vars(args.featurizer_kwargs), args.parallel, client_kwargs,
         view_flags, args.compression_level, args.chiral_scaffolds)
