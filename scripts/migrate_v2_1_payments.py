"""
Script de migration V2.1 — Paiements Mobile Money :
- Création de l'enum PostgreSQL payment_status (8 statuts)
- Ajout des colonnes payment_status et payment_method sur orders
- Ajout des colonnes payment_method et payment_reference sur invoices
- Création de la table payments avec indexation et contrainte d'idempotence (provider_event_id)

Usage : python scripts/migrate_v2_1_payments.py
"""

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import engine

use_selector_event_loop_on_windows()


async def migrate_v2_1_payments():
    print("🚀 Exécution de la migration V2.1 — Paiements Mobile Money...")
    async with engine.begin() as conn:
        # 1. Enum PostgreSQL payment_status
        await conn.execute(
            text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
                    CREATE TYPE payment_status AS ENUM (
                        'initiated',
                        'pending_validation',
                        'processing',
                        'success',
                        'failed',
                        'cancelled',
                        'expired',
                        'refunded'
                    );
                END IF;
            END $$;
            """)
        )
        print("   ✅ Type ENUM payment_status vérifié/créé.")

        # 2. Colonnes sur orders
        await conn.execute(
            text("""
            ALTER TABLE orders
                ADD COLUMN IF NOT EXISTS payment_status VARCHAR(32) NOT NULL DEFAULT 'unpaid',
                ADD COLUMN IF NOT EXISTS payment_method VARCHAR(32) NULL;
            """)
        )
        print("   ✅ Colonnes de paiement ajoutées sur orders.")

        # 3. Colonnes sur invoices
        await conn.execute(
            text("""
            ALTER TABLE invoices
                ADD COLUMN IF NOT EXISTS payment_method VARCHAR(32) NULL,
                ADD COLUMN IF NOT EXISTS payment_reference VARCHAR(64) NULL;
            """)
        )
        print("   ✅ Colonnes de paiement ajoutées sur invoices.")

        # 4. Table payments
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS payments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                provider VARCHAR(32) NOT NULL DEFAULT 'mock',
                amount NUMERIC(12, 2) NOT NULL,
                currency VARCHAR(8) NOT NULL DEFAULT 'XOF',
                status payment_status NOT NULL DEFAULT 'initiated',
                transaction_reference VARCHAR(64) NOT NULL UNIQUE,
                provider_tx_id VARCHAR(128) NULL,
                provider_event_id VARCHAR(128) NULL UNIQUE,
                customer_phone VARCHAR(32) NULL,
                checkout_url VARCHAR(500) NULL,
                qr_code_url VARCHAR(500) NULL,
                paid_at TIMESTAMPTZ NULL,
                raw_metadata JSONB NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS ix_payments_business_id ON payments (business_id);
            CREATE INDEX IF NOT EXISTS ix_payments_order_id ON payments (order_id);
            CREATE INDEX IF NOT EXISTS ix_payments_customer_id ON payments (customer_id);
            CREATE INDEX IF NOT EXISTS ix_payments_status ON payments (status);
            CREATE INDEX IF NOT EXISTS ix_payments_transaction_reference ON payments (transaction_reference);
            CREATE INDEX IF NOT EXISTS ix_payments_provider_tx_id ON payments (provider_tx_id);
            CREATE INDEX IF NOT EXISTS ix_payments_provider_event_id ON payments (provider_event_id);
            """)
        )
        print("   ✅ Table payments et index créés avec succès.")

    print("🎉 Migration V2.1 terminée avec succès !")


if __name__ == "__main__":
    asyncio.run(migrate_v2_1_payments())
