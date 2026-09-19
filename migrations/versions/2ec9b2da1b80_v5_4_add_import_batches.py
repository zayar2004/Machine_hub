"""V5.4 add import_batches

Revision ID: 2ec9b2da1b80
Revises: 83ae27482789
Create Date: 2026-09-18 21:08:42.011828

"""
from alembic import op
import sqlalchemy as sa


revision = '2ec9b2da1b80'
down_revision = '83ae27482789'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create import_batches table with NAMED constraints
    op.create_table(
        'import_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('machine_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ACTIVE'),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['created_by'], ['users.id'],
            name='fk_import_batches_created_by',
            ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['shop_id'], ['shops.id'],
            name='fk_import_batches_shop_id',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name='pk_import_batches'),
    )

    # 2. Indexes on import_batches
    with op.batch_alter_table('import_batches', schema=None) as batch_op:
        batch_op.create_index(
            'ix_import_batches_shop_id', ['shop_id'], unique=False,
        )
        batch_op.create_index(
            'ix_import_batches_status', ['status'], unique=False,
        )

    # 3. Add batch_id to machines with NAMED FK
    with op.batch_alter_table('machines', schema=None) as batch_op:
        batch_op.add_column(sa.Column('batch_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            'ix_machines_batch_id', ['batch_id'], unique=False,
        )
        batch_op.create_foreign_key(
            'fk_machines_batch_id_import_batches',
            'import_batches',
            ['batch_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('machines', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_machines_batch_id_import_batches', type_='foreignkey',
        )
        batch_op.drop_index('ix_machines_batch_id')
        batch_op.drop_column('batch_id')

    with op.batch_alter_table('import_batches', schema=None) as batch_op:
        batch_op.drop_index('ix_import_batches_status')
        batch_op.drop_index('ix_import_batches_shop_id')

    op.drop_table('import_batches')
