"""Application services package initialization."""
from services.tax_service import tax_service, TaxService
from services.catalogue_service import catalogue_service, CatalogueService
from services.inventory_service import inventory_service, InventoryService
from services.billing_service import billing_service, BillingService
from services.company_service import company_service, CompanyService
from services.account_service import account_service, AccountService
from services.printing_service import printing_service, PrintingService
from services.backup_service import backup_service, BackupService
from services.reporting_service import reporting_service, ReportingService
from services.migration_service import migration_service, MigrationService

__all__ = [
    "tax_service", "TaxService",
    "catalogue_service", "CatalogueService",
    "inventory_service", "InventoryService",
    "billing_service", "BillingService",
    "company_service", "CompanyService",
    "account_service", "AccountService",
    "printing_service", "PrintingService",
    "backup_service", "BackupService",
    "reporting_service", "ReportingService",
    "migration_service", "MigrationService"
]
