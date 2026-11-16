"""Atividades extra: definições por turma, poker (mesas, lugares, mãos, ações, eventos, consentimento) e Bit a Bit.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-16 09:03:19.749137
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('bitabit_games',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('class_id', sa.Integer(), nullable=True),
    sa.Column('seed', sa.BigInteger(), nullable=False),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('valid', sa.Boolean(), nullable=True),
    sa.Column('answers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bitabit_user', 'bitabit_games', ['user_id', 'finished_at'], unique=False)
    op.create_table('poker_consent',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('extra_settings',
    sa.Column('class_id', sa.Integer(), nullable=False),
    sa.Column('poker_enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('poker_source', sa.String(length=12), server_default='torneios', nullable=False),
    sa.Column('students_can_create_tables', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('max_tables', sa.Integer(), server_default='4', nullable=False),
    sa.Column('buy_in_min', sa.Integer(), server_default='10', nullable=False),
    sa.Column('buy_in_max', sa.Integer(), server_default='200', nullable=False),
    sa.Column('buy_in_max_pct', sa.Integer(), server_default='50', nullable=False),
    sa.Column('daily_loss_limit', sa.Integer(), server_default='100', nullable=False),
    sa.Column('bitabit_daily_cap', sa.Integer(), server_default='50', nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['school_classes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('class_id')
    )
    op.create_table('poker_tables',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('class_id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
    sa.Column('max_seats', sa.Integer(), nullable=False),
    sa.Column('small_blind', sa.Integer(), nullable=False),
    sa.Column('big_blind', sa.Integer(), nullable=False),
    sa.Column('state', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('dealer_seat', sa.Integer(), nullable=True),
    sa.Column('hand_no', sa.Integer(), nullable=False),
    sa.Column('next_hand_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('turn_deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('current_hand_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['class_id'], ['school_classes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_poker_tables_class_id'), 'poker_tables', ['class_id'], unique=False)
    op.create_table('poker_events',
    sa.Column('seq', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['table_id'], ['poker_tables.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('seq')
    )
    op.create_index('ix_poker_events_table_seq', 'poker_events', ['table_id', 'seq'], unique=False)
    op.create_table('poker_hands',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('hand_no', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dealer_seat', sa.Integer(), nullable=False),
    sa.Column('state', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['table_id'], ['poker_tables.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_poker_hands_table', 'poker_hands', ['table_id', 'hand_no'], unique=False)
    op.create_table('poker_seats',
    sa.Column('table_id', sa.Integer(), nullable=False),
    sa.Column('seat', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('stack', sa.Integer(), nullable=False),
    sa.Column('buy_in', sa.Integer(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
    sa.Column('away_hands', sa.Integer(), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['table_id'], ['poker_tables.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('table_id', 'seat'),
    sa.UniqueConstraint('user_id', name='uq_poker_seat_user')
    )
    op.create_table('poker_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hand_id', sa.Integer(), nullable=False),
    sa.Column('seq', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('seat', sa.Integer(), nullable=False),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('street', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('action_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    sa.Column('auto', sa.Boolean(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['hand_id'], ['poker_hands.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hand_id', 'action_id', name='uq_poker_action_id')
    )
    op.create_index(op.f('ix_poker_actions_hand_id'), 'poker_actions', ['hand_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_poker_actions_hand_id'), table_name='poker_actions')
    op.drop_table('poker_actions')
    op.drop_table('poker_seats')
    op.drop_index('ix_poker_hands_table', table_name='poker_hands')
    op.drop_table('poker_hands')
    op.drop_index('ix_poker_events_table_seq', table_name='poker_events')
    op.drop_table('poker_events')
    op.drop_index(op.f('ix_poker_tables_class_id'), table_name='poker_tables')
    op.drop_table('poker_tables')
    op.drop_table('extra_settings')
    op.drop_table('poker_consent')
    op.drop_index('ix_bitabit_user', table_name='bitabit_games')
    op.drop_table('bitabit_games')
