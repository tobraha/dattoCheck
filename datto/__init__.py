"""Module 'datto'

base.py:
class DattoAsset() - normalize json-type data from a Datto Asset\
from the Datto API.

datto.py:
class Datto() - session & communication with the API
class DattoCheck() - operational functions to run the checks"""

from .datto import DattoCheck
