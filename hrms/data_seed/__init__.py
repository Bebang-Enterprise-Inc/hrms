"""S181 reference CSVs that ship inside the hrms Python package.

The top-level `data/` directory in the hrms repo is gitignored, so static
reference files needed at runtime (S037 store-buyer-entity register, BIR
TIN/RDO register, Mosaic POS keys, Bebang Halo-Halo store locations)
must live INSIDE the Python package to make it into the Frappe Docker
image when GitHub Actions clones the repo.

This module is intentionally empty -- it just makes the directory a
Python package so the CSVs are picked up by `setuptools.find_packages`
and any consumer can resolve them via
`frappe.get_app_path("hrms", "data_seed", "<filename>")`.

Files in this directory:
  store_buyer_entity_register_2026-03-12.csv  -- 48 stores -> buyer entities
  ENTITY_TIN_RDO_2026-02-27.csv               -- 51 BIR TIN/RDO entries
  MOSAIC_POS_API_KEYS.csv                     -- 45 stores -> Mosaic location_id
  Bebang_Halo-Halo_Stores_Locations_2025-12-29.csv  -- 42 stores -> public GPS

When the underlying source data changes, replace the file here and bump
the date in the filename. Code paths use the explicit dated filename so
old data continues to work until the consumer is updated.
"""
