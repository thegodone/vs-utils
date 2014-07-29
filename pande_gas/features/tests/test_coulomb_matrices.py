"""
Tests for Coulomb matrix calculation.
"""
import numpy as np
import unittest

from rdkit import Chem
from rdkit_utils import conformers

from pande_gas.features import coulomb_matrices as cm


class TestCoulombMatrix(unittest.TestCase):
    """
    Tests for CoulombMatrix.
    """
    def setUp(self):
        """
        Set up tests.
        """
        smiles = 'CC(=O)OC1=CC=CC=C1C(=O)O'
        mol = Chem.MolFromSmiles(smiles)
        engine = conformers.ConformerGenerator(max_conformers=1)
        self.mol = engine.generate_conformers(mol)
        assert self.mol.GetNumConformers() > 0

    def test_coulomb_matrix(self):
        """Test CoulombMatrix."""
        f = cm.CoulombMatrix(self.mol.GetNumAtoms())
        rval = f([self.mol])
        size = np.triu_indices(self.mol.GetNumAtoms())[0].size
        assert rval.shape == (1, self.mol.GetNumConformers(), size)

    def test_coulomb_matrix_padding(self):
        """Test CoulombMatrix with padding."""
        f = cm.CoulombMatrix(max_atoms=self.mol.GetNumAtoms() * 2)
        rval = f([self.mol])
        size = np.triu_indices(self.mol.GetNumAtoms() * 2)[0].size
        assert rval.shape == (1, self.mol.GetNumConformers(), size)
