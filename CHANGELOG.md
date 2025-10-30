# Changelog

## 2025-11-17 - Project Reorganization

### Changed
- **Reorganized file structure** for better maintainability
  - Moved all main scripts to `scripts/` folder
  - Moved utility scripts to `utils/` folder
  - Updated all batch files and documentation to use new paths
  
### Removed
- Deleted development trail files:
  - `sku_mapping_generated.csv` (moved to examples/)
  - `sku_mapping_generated_clean.csv` (moved to examples/)
  - `sku_mapping_high_medium.csv` (moved to examples/)
  - `PRODUCT_MAPPING_RESULTS.txt`
  - `MAPPING_GENERATOR_README.txt`

### Added
- **Separate IIF files workflow**:
  - `*_NEW_CUSTOMERS.iif` - Customer records with tax codes
  - `*_INVOICES.iif` - Invoices with Ship To addresses
- **Discount tracking**: Captures discount codes and gift cards as "Non-inventory Item"
- **Freight line**: Always included on every invoice (even $0 shipping)
- **Duplicate prevention**: `import_log.csv` tracks all imported orders
- **Tax code assignment**: Automatic in-state/out-of-state tax codes for new customers
- `PROJECT_STRUCTURE.md` - Visual documentation of folder structure

### Fixed
- Invoice line items now use customer tax codes instead of per-item taxable flags
- Ship To address now properly captured on all invoices
- Product mapping uses correct QB items ("Non-inventory Item" and "Freight")

## Migration Notes

**To use the reorganized structure:**

1. Update your Task Scheduler or automation tools to use:
   - `python scripts\squarespace_to_quickbooks.py` (instead of root)
   - Batch files automatically updated

2. Import workflow changed to two-step:
   - Import `*_NEW_CUSTOMERS.iif` first (if exists)
   - Then import `*_INVOICES.iif`

3. All functionality remains the same, just better organized!
