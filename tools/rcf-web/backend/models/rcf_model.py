"""
RCF (Radiochromic Film) Data Model

Represents a radiochromic film detector with its properties and response data.

Author: Tan Song
"""

import numpy as np


class RCF:
    """
    Represents a Radiochromic Film detector.

    This class encapsulates the properties and behavior of RCF detectors
    including energy deposition calculations and cutoff energy determination.

    Attributes:
        name (str): Detector material name (e.g., 'HD', 'EBT', 'Cu', 'Cr')
        rcfid (int): Unique identifier for the detector
        table_ID (int): Position in the detector stack
        energy_zoom (list): Energy values where particles are detected
        edep_zoom (np.ndarray): Energy deposition data [N x 2] array
                               Column 0: Input energy
                               Column 1: Deposited energy
        Ein_stoppos (np.ndarray): Input energy and stopping position data [N x 2]
                                  Column 0: Input energy
                                  Column 1: Stopping position (layer index)
        Cutoff_ene (float): Cutoff energy for this detector (MeV)
                           The energy at which maximum deposition occurs
    """

    def __init__(self, name, rcfid, table_ID):
        """
        Initialize an RCF detector

        Args:
            name (str): Detector material name ('HD', 'EBT', 'Cu', 'Cr')
            rcfid (int): Unique identifier for this detector
            table_ID (int): Position in the detector stack table
        """
        self.name = name
        self.rcfid = rcfid
        self.table_ID = table_ID
        self.energy_zoom = []
        self.edep_zoom = None
        self.Ein_stoppos = None
        self.Cutoff_ene = None

    def __repr__(self):
        """String representation for debugging"""
        cutoff_str = f"{self.Cutoff_ene:.2f} MeV" if self.Cutoff_ene is not None else "Not calculated"
        return (f"RCF(name='{self.name}', id={self.rcfid}, "
                f"table_pos={self.table_ID}, cutoff={cutoff_str})")

    def initialize_arrays(self, energy_range):
        """
        Initialize energy deposition and stopping position arrays

        Args:
            energy_range (np.ndarray): Array of input energies to scan
        """
        n_energies = len(energy_range)
        self.Ein_stoppos = np.column_stack((energy_range, np.full(n_energies, float('inf'))))
        self.edep_zoom = np.column_stack((energy_range, np.full(n_energies, float('inf'))))
        self.energy_zoom = []

    def record_deposition(self, energy_index, stop_position, energy_deposited):
        """
        Record energy deposition data for a specific input energy

        Args:
            energy_index (int): Index in the energy scan array
            stop_position (float): Layer where particle stopped
            energy_deposited (float): Energy deposited in this detector (MeV)
        """
        if self.Ein_stoppos is not None and self.edep_zoom is not None:
            self.Ein_stoppos[energy_index, 1] = stop_position
            self.edep_zoom[energy_index, 1] = energy_deposited

    def add_detection_energy(self, energy):
        """
        Add an energy value where the detector successfully detected the particle

        Args:
            energy (float): Input energy that was detected (MeV)
        """
        energy_rounded = round(energy, 1)
        self.energy_zoom.append(energy_rounded)

    def calculate_cutoff_energy(self, energy_range):
        """
        Calculate the cutoff energy (energy with maximum deposition)

        Args:
            energy_range (np.ndarray): Array of input energies

        Returns:
            float: Cutoff energy (MeV), or None if no valid data
        """
        if self.edep_zoom is None or len(self.edep_zoom) == 0:
            return None

        edep = self.edep_zoom[:, 1].copy()  # Deposited energy
        edep[edep == np.inf] = 0

        if np.all(edep == 0):
            return None

        index_max = np.argmax(edep)
        self.Cutoff_ene = energy_range[index_max]
        return self.Cutoff_ene

    def get_response_curve(self):
        """
        Get the energy deposition response curve

        Returns:
            tuple: (energies, depositions) where energies is input energy array
                   and depositions is deposited energy array
        """
        if self.edep_zoom is None:
            return None, None

        energies = self.edep_zoom[:, 0]
        depositions = self.edep_zoom[:, 1].copy()
        depositions[depositions == np.inf] = 0

        return energies, depositions

    def is_valid_detection(self, stop_position, detector_type=None):
        """
        Check if particle stopping at given position constitutes valid detection

        Args:
            stop_position (int): Layer index where particle stopped
            detector_type (str): Type of detector ('HD', 'EBT'). If None, uses self.name

        Returns:
            bool: True if valid detection, False otherwise
        """
        if detector_type is None:
            detector_type = self.name

        if detector_type == 'HD':
            return stop_position <= 7
        elif detector_type == 'EBT':
            return stop_position <= 29
        elif detector_type in ['Cu', 'Cr']:
            # For metal detectors, typically check against their thickness
            # This is a simplified check
            return True
        else:
            return False

    def to_dict(self):
        """
        Convert RCF object to dictionary for JSON serialization

        Returns:
            dict: Dictionary representation of RCF
        """
        return {
            "rcf_id": self.rcfid,
            "table_ID": self.table_ID,
            "Cutoff_ene": self.Cutoff_ene
        }

    @classmethod
    def from_dict(cls, name, data):
        """
        Create RCF object from dictionary

        Args:
            name (str): Detector name
            data (dict): Dictionary containing RCF data

        Returns:
            RCF: Reconstructed RCF object
        """
        rcf = cls(name, data["rcf_id"], data["table_ID"])
        rcf.Cutoff_ene = data.get("Cutoff_ene")
        return rcf
