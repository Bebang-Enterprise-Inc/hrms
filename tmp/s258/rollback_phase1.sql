-- S258 Phase 1 rollback SQL — generated 2026-06-04T17:28:05+0800
-- Apply only if Phase 1 fails mid-execution.

-- Rollback for ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC (ARGW):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC';

-- Rollback for AYALA EVO CITY - BEBANG MEGA INC. (AYEVO):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'AYALA EVO CITY - BEBANG MEGA INC.';

-- Rollback for AYALA FAIRVIEW TERRACES - BEBANG FT INC. (AFT):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'AYALA FAIRVIEW TERRACES - BEBANG FT INC.';

-- Rollback for AYALA MARKET MARKET - BEBANG MARKET MARKET INC. (AMM):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'AYALA MARKET MARKET - BEBANG MARKET MARKET INC.';

-- Rollback for AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC. (AYSOL):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'AYALA SOLENAD - HFFM SOLENAD FOOD SERVICES INC.';

-- Rollback for AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC. (UPTC):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'AYALA UP TOWN CENTER - BEBANG UP TOWN CENTER INC.';

-- Rollback for BF HOMES - BEBANG BF HOMES INC. (BFH):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'BF HOMES - BEBANG BF HOMES INC.';

-- Rollback for CTTM TOMAS MORATO - B CUBED VENTURES CORP. (CTTM):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'CTTM TOMAS MORATO - B CUBED VENTURES CORP.';

-- Rollback for D'VERDE CALAMBA - TAJ FOOD CORP. (DVCAL):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'D''VERDE CALAMBA - TAJ FOOD CORP.';

-- Rollback for EVER COMMONWEALTH - DLS DESSERT CRAFT INC. (EGC):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'EVER COMMONWEALTH - DLS DESSERT CRAFT INC.';

-- Rollback for FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC. (FMA):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'FESTIVAL MALL ALABANG - BEBANG FESTIVAL INC.';

-- Rollback for IRRESISTIBLE INFUSIONS INC. (III):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'IRRESISTIBLE INFUSIONS INC.';
DELETE FROM `tabAccount` WHERE name = 'Stock In Hand - III';

-- Rollback for LEGACY77 FOOD CORP. (L77):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'LEGACY77 FOOD CORP.';

-- Rollback for LUCKY CHINATOWN - BEBANG LCT INC. (LCT):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'LUCKY CHINATOWN - BEBANG LCT INC.';

-- Rollback for MEGAWIDE PITX - BEBANG PITX INC. (PTX):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'MEGAWIDE PITX - BEBANG PITX INC.';

-- Rollback for MEGAWORLD PASEO CENTER - BEBANG PASEO INC. (MPD):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'MEGAWORLD PASEO CENTER - BEBANG PASEO INC.';

-- Rollback for MEGAWORLD VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC. (VGC):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'MEGAWORLD VENICE GRAND CANAL - BEBANG VENICE GRAND CANAL INC.';

-- Rollback for NAIA T3 - HALO-HALO TERMINAL FOOD CORP. (NAIA):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'NAIA T3 - HALO-HALO TERMINAL FOOD CORP.';

-- Rollback for ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP. (ESM):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP.';

-- Rollback for ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC (ROBGS):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'ROBINSONS GALLERIA SOUTH - TUNGSTEN CAPITAL HOLDINGS OPC';

-- Rollback for ROBINSONS GENERAL TRIAS - BEBANG MEGA INC. (ROBGT):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'ROBINSONS GENERAL TRIAS - BEBANG MEGA INC.';

-- Rollback for ROBINSONS IMUS - BEBANG MEGA INC. (ROBIM):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'ROBINSONS IMUS - BEBANG MEGA INC.';

-- Rollback for ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC. (ROBDA):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'ROBINSONS PLACE DASMARINAS - FREEZE DELIGHT INC.';

-- Rollback for SM BICUTAN - BEBANG SM BICUTAN INC. (SMBIC):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM BICUTAN - BEBANG SM BICUTAN INC.';

-- Rollback for SM CALOOCAN - TAJ FOOD CORP. (SMCAL):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM CALOOCAN - TAJ FOOD CORP.';

-- Rollback for SM CLARK - RED TALDAWA FOODS OPC (SMCLK):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM CLARK - RED TALDAWA FOODS OPC';

-- Rollback for SM EAST ORTIGAS - BEBANG SMEO INC. (SMEO):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM EAST ORTIGAS - BEBANG SMEO INC.';

-- Rollback for SM GRAND CENTRAL - BEBANG GRAND CENTRAL INC. (SMGC):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM GRAND CENTRAL - BEBANG GRAND CENTRAL INC.';

-- Rollback for SM MALL OF ASIA - BEBANG SMOA INC. (SMMOA):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM MALL OF ASIA - BEBANG SMOA INC.';

-- Rollback for SM MARILAO - BEBANG MARILAO INC. (SMMAR):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM MARILAO - BEBANG MARILAO INC.';

-- Rollback for SM NORTH EDSA - BEBANG NORTH EDSA INC. (SMNE):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM NORTH EDSA - BEBANG NORTH EDSA INC.';

-- Rollback for SM PULILAN - BEBANG SMM INC. (SMPUL):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM PULILAN - BEBANG SMM INC.';

-- Rollback for SM SAN JOSE DEL MONTE - JL TRADE OPC (SJDM):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM SAN JOSE DEL MONTE - JL TRADE OPC';

-- Rollback for SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC (SMSDN):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM SANGANDAAN - TUNGSTEN CAPITAL HOLDINGS OPC';

-- Rollback for SM STA. ROSA - SWEET HARMONY FOOD CORP. (SMSTR):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM STA. ROSA - SWEET HARMONY FOOD CORP.';

-- Rollback for SM TANZA - BEBANG MEGA INC. (SMTZ):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM TANZA - BEBANG MEGA INC.';

-- Rollback for SM TAYTAY - DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP. (SMTAY):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM TAYTAY - DAY ONES FOOD AND DRINK ESTABLISHMENTS CORP.';

-- Rollback for SM VALENZUELA - BEBANG SMV INC. (SMV):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'SM VALENZUELA - BEBANG SMV INC.';

-- Rollback for STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC. (SLGM):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'STA. LUCIA EAST GRAND MALL - BEBANG SM MARIKINA INC.';

-- Rollback for THE GRID ROCKWELL - TASTECARTEL CORP. (TGR):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'THE GRID ROCKWELL - TASTECARTEL CORP.';

-- Rollback for THE TERMINAL - BEBANG STARMALL ALABANG INC. (TTA):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'THE TERMINAL - BEBANG STARMALL ALABANG INC.';

-- Rollback for UP TOWN MALL BGC - DMD HOLDINGS INC. (UMBGC):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'UP TOWN MALL BGC - DMD HOLDINGS INC.';

-- Rollback for VISTA MALL TAGUIG - TRICERN FOOD CORP. (VMTAG):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'VISTA MALL TAGUIG - TRICERN FOOD CORP.';

-- Rollback for XENTROMALL MONTALBAN - PERPETUAL FOOD CORP. (XMM):
UPDATE `tabCompany` SET default_inventory_account = NULL WHERE name = 'XENTROMALL MONTALBAN - PERPETUAL FOOD CORP.';

-- A2 rollback for L77:
UPDATE `tabCompany` SET stock_received_but_not_billed = NULL WHERE name = 'LEGACY77 FOOD CORP.';

