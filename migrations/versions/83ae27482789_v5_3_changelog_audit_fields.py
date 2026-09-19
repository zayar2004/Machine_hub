"""V5.3 changelog audit fields

Revision ID: 83ae27482789
Revises: 6ab1d4de20f5
Create Date: 2026-09-18 19:53:03.032987

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '83ae27482789'
down_revision = '6ab1d4de20f5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('change_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('user_label', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('detail', sa.String(length=500), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_change_logs_user_id'),
            ['user_id'],
            unique=False,
        )
        batch_op.create_foreign_key(
            'fk_change_logs_user_id',
            'users',
            ['user_id'],
            ['id'],
            ondelete='SET NULL',
        )


def downgrade():
    with op.batch_alter_table('change_logs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_change_logs_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_change_logs_user_id'))
        batch_op.drop_column('detail')
        batch_op.drop_column('user_label')
        batch_op.drop_column('user_id')
