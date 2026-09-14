"""
Script de migration V2.0 Logistique :
- Ajout du rôle livreur et des attributs livreur sur la table users.
- Création de la table delivery_partners (flottes/agences tierces à Bamako).
- Création de la table delivery_missions (missions, statuts, OTP, géolocalisation).

Usage : python scripts/migrate_v2_logistics.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.asyncio_compat import use_selector_event_loop_on_windows
from app.db.session import engine

use_selector_event_loop_on_windows()


async def migrate_v2_logistics():
    print("Execution de la migration V2.0 Logistique & Flotte...")
    async with engine.begin() as conn:
        # 1. Enums PostgreSQL
        await conn.execute(
            text("""
            DO $$
            BEGIN
                -- Mise a jour du type user_role pour inclure 'livreur'
                ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'livreur';
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;

            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'driver_type') THEN
                    CREATE TYPE driver_type AS ENUM ('internal', 'partner');
                END IF;
            END $$;

            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assignment_type') THEN
                    CREATE TYPE assignment_type AS ENUM ('internal', 'partner');
                END IF;
            END $$;

            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mission_status') THEN
                    CREATE TYPE mission_status AS ENUM (
                        'pending', 'assigned', 'picked_up', 'in_transit', 'en_route', 'delivered', 'failed', 'cancelled'
                    );
                ELSE
                    ALTER TYPE mission_status ADD VALUE IF NOT EXISTS 'in_transit';
                    ALTER TYPE mission_status ADD VALUE IF NOT EXISTS 'en_route';
                END IF;
            END $$;
        """)
        )

        # 2. Enrichissement de la table users
        await conn.execute(
            text("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number VARCHAR(50);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS driver_type driver_type;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS is_available BOOLEAN NOT NULL DEFAULT TRUE;
        """)
        )

        # 3. Table delivery_partners
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS delivery_partners (
                id UUID PRIMARY KEY,
                business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                contact_name VARCHAR(150),
                phone_number VARCHAR(50) NOT NULL,
                address VARCHAR(255),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS ix_delivery_partners_business_id ON delivery_partners(business_id);
        """)
        )

        # 4. Table delivery_missions
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS delivery_missions (
                id UUID PRIMARY KEY,
                business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                assignment_type assignment_type NOT NULL DEFAULT 'internal',
                status mission_status NOT NULL DEFAULT 'pending',
                driver_id UUID REFERENCES users(id) ON DELETE SET NULL,
                partner_id UUID REFERENCES delivery_partners(id) ON DELETE SET NULL,
                delivery_zone_id UUID REFERENCES delivery_zones(id) ON DELETE SET NULL,
                pickup_address VARCHAR(500) NOT NULL,
                delivery_address VARCHAR(500) NOT NULL,
                customer_name VARCHAR(150),
                customer_phone VARCHAR(50) NOT NULL,
                otp_code VARCHAR(10) NOT NULL,
                otp_verified BOOLEAN NOT NULL DEFAULT FALSE,
                current_latitude NUMERIC(10, 7),
                current_longitude NUMERIC(10, 7),
                assigned_at TIMESTAMPTZ,
                picked_up_at TIMESTAMPTZ,
                delivered_at TIMESTAMPTZ,
                notes TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            -- S'assurer que toutes les colonnes existent au cas où la table pré-existait
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS assignment_type assignment_type NOT NULL DEFAULT 'internal';
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS status mission_status NOT NULL DEFAULT 'pending';
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS driver_id UUID REFERENCES users(id) ON DELETE SET NULL;
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS partner_id UUID REFERENCES delivery_partners(id) ON DELETE SET NULL;
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS delivery_zone_id UUID REFERENCES delivery_zones(id) ON DELETE SET NULL;
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS pickup_address VARCHAR(500);
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS delivery_address VARCHAR(500);
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS customer_name VARCHAR(150);
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(50);
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS otp_code VARCHAR(10);
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS otp_verified BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS current_latitude NUMERIC(10, 7);
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS current_longitude NUMERIC(10, 7);
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS assigned_at TIMESTAMPTZ;
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS picked_up_at TIMESTAMPTZ;
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;
            ALTER TABLE delivery_missions ADD COLUMN IF NOT EXISTS notes TEXT;

            -- Si d'anciennes colonnes existaient avec contrainte NOT NULL, les rendre nullables
            DO $$
            DECLARE
                col RECORD;
            BEGIN
                FOR col IN
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'delivery_missions'
                      AND is_nullable = 'NO'
                      AND column_name NOT IN ('id', 'business_id', 'order_id')
                LOOP
                    EXECUTE format('ALTER TABLE delivery_missions ALTER COLUMN %I DROP NOT NULL', col.column_name);
                END LOOP;
            END $$;

            CREATE INDEX IF NOT EXISTS ix_delivery_missions_business_id ON delivery_missions(business_id);
            CREATE INDEX IF NOT EXISTS ix_delivery_missions_order_id ON delivery_missions(order_id);
            CREATE INDEX IF NOT EXISTS ix_delivery_missions_status ON delivery_missions(status);
            CREATE INDEX IF NOT EXISTS ix_delivery_missions_driver_id ON delivery_missions(driver_id);
            CREATE INDEX IF NOT EXISTS ix_delivery_missions_partner_id ON delivery_missions(partner_id);
        """)
        )

    print("[SUCCESS] Migration V2.0 Logistique achevee avec succes.")


if __name__ == "__main__":
    asyncio.run(migrate_v2_logistics())
