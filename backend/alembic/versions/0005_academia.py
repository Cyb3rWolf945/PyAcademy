"""Academia: progresso por secção, registo das atividades e decks de slides.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-15 17:17:36.753845
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('slide_decks',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
    sa.Column('titulo', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('n_slides', sa.Integer(), nullable=False),
    sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('academy_activity_log',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('section_id', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
    sa.Column('activity_idx', sa.Integer(), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('solved_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'section_id', 'activity_idx')
    )
    op.create_table('academy_progress',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('section_id', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verify_attempts', sa.Integer(), nullable=False),
    sa.Column('hints_used', sa.Integer(), nullable=False),
    sa.Column('first_try', sa.Boolean(), server_default='false', nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'section_id')
    )


def downgrade() -> None:
    op.drop_table('academy_progress')
    op.drop_table('academy_activity_log')
    op.drop_table('slide_decks')
