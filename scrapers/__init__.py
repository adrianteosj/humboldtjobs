from .base import BaseScraper, JobData
from .neogov import NEOGOVScraper
from .csu import CSUScraper
from .edjoin import EdJoinScraper
from .arcata import ArcataScraper
from .civicplus import WiyotScraper, RioDellScraper
from .redwoods import RedwoodsScraper
from .lostcoast import LostCoastOutpostScraper
from .small_cities import BlueLakeScraper, FerndaleScraper, TrinidadScraper

# Tier 2 - Healthcare
from .workday import OpenDoorHealthScraper, WorkdayScraper
from .healthcare import (
    ProvidenceScraper,
    MadRiverHospitalScraper,
    UnitedIndianHealthScraper,
    KimawMedicalScraper,
    HospiceOfHumboldtScraper,
    HumboldtSeniorResourceScraper,
    RCAAScraper,
    SoHumHealthScraper,
)

# Tier 3 - Local Employers
from .local_employers import (
    BlueLakeCasinoScraper,
    BearRiverCasinoScraper,
    GreenDiamondScraper,
    NorthCoastCoopScraper,
    LACOAssociatesScraper,
    EurekaNaturalFoodsScraper,
    DancoGroupScraper,
)

# Tier 3B - National Retailers
from .national_retailers import (
    DollarGeneralScraper,
    WalgreensScraper,
    TJMaxxScraper,
    CostcoScraper,
    SafewayScraper,
    WalmartScraper,
)

# Tier 3B - Banks and Financial Institutions
from .banks import (
    CoastCentralCUScraper,
    CompassCCUScraper,
    TriCountiesBankScraper,
    RedwoodCapitalBankScraper,
    ColumbiaBankScraper,
)

# Tier 3B - Nonprofit and Social Services
from .nonprofits import (
    RRHCScraper,
    TwoFeathersScraper,
    ChangingTidesScraper,
)

# Tier 3C - Additional Local and Regional Employers
from .tier3_employers import (
    RCEAScraper,
    FoodForPeopleScraper,
    BGCRedwoodsScraper,
    KokatatScraper,
    LostCoastBreweryScraper,
    MurphysMarketsScraper,
    CypressGroveScraper,
    DriscollsScraper,
    WinCoFoodsScraper,
    GroceryOutletScraper,
    HarborFreightScraper,
    AceHardwareScraper,
    SierraPacificScraper,
    CVSHealthScraper,
    RiteAidScraper,
    StarbucksScraper,
    FedExScraper,
    UPSScraper,
    PGEScraper,
    HumboldtSawmillScraper,
    HumboldtCreameryScraper,
    AlexandreFamilyFarmScraper,
    PacificSeafoodScraper,
    ArcataHouseScraper,
    PiersonBuildingScraper,
    CCraneScraper,
    JonesFamilyTreeServiceScraper,
)

__all__ = [
    'BaseScraper',
    'JobData',
    # Tier 1 - Government/Education
    'NEOGOVScraper',
    'CSUScraper',
    'EdJoinScraper',
    'ArcataScraper',
    # Tier 2 - Tribal/Community
    'WiyotScraper',
    'RioDellScraper',
    'RedwoodsScraper',
    'LostCoastOutpostScraper',
    # Tier 2 - Small Cities
    'BlueLakeScraper',
    'FerndaleScraper',
    'TrinidadScraper',
    # Tier 2 - Healthcare (Workday)
    'OpenDoorHealthScraper',
    'WorkdayScraper',
    # Tier 2 - Healthcare (Other)
    'ProvidenceScraper',
    'MadRiverHospitalScraper',
    'UnitedIndianHealthScraper',
    'KimawMedicalScraper',
    'HospiceOfHumboldtScraper',
    'HumboldtSeniorResourceScraper',
    'RCAAScraper',
    'SoHumHealthScraper',
    # Tier 3 - Local Employers
    'BlueLakeCasinoScraper',
    'BearRiverCasinoScraper',
    'GreenDiamondScraper',
    'NorthCoastCoopScraper',
    'LACOAssociatesScraper',
    'EurekaNaturalFoodsScraper',
    'DancoGroupScraper',
    # Tier 3B - National Retailers
    'DollarGeneralScraper',
    'WalgreensScraper',
    'TJMaxxScraper',
    'CostcoScraper',
    'SafewayScraper',
    'WalmartScraper',
    # Tier 3B - Banks and Financial Institutions
    'CoastCentralCUScraper',
    'CompassCCUScraper',
    'TriCountiesBankScraper',
    'RedwoodCapitalBankScraper',
    'ColumbiaBankScraper',
    # Tier 3B - Nonprofit and Social Services
    'RRHCScraper',
    'TwoFeathersScraper',
    'ChangingTidesScraper',
    # Tier 3C - Additional Local and Regional Employers
    'RCEAScraper',
    'FoodForPeopleScraper',
    'BGCRedwoodsScraper',
    'KokatatScraper',
    'LostCoastBreweryScraper',
    'MurphysMarketsScraper',
    'CypressGroveScraper',
    'DriscollsScraper',
    'WinCoFoodsScraper',
    'GroceryOutletScraper',
    'HarborFreightScraper',
    'AceHardwareScraper',
    'SierraPacificScraper',
    'CVSHealthScraper',
    'RiteAidScraper',
    'StarbucksScraper',
    'FedExScraper',
    'UPSScraper',
    'PGEScraper',
    'HumboldtSawmillScraper',
    'HumboldtCreameryScraper',
    'AlexandreFamilyFarmScraper',
    'PacificSeafoodScraper',
    'ArcataHouseScraper',
    'PiersonBuildingScraper',
    'CCraneScraper',
    'JonesFamilyTreeServiceScraper',
]
