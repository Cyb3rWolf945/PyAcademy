"""Eliminatória: grupos, livro de pontos pessoais (user_points), estado dos jogadores e flag do leaderboard público.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-15 11:39:01.895722
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('user_points',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('tournament_id', sa.Integer(), nullable=True),
    sa.Column('round_idx', sa.Integer(), nullable=True),
    sa.Column('problem_slug', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_points_created', 'user_points', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_points_user_id'), 'user_points', ['user_id'], unique=False)
    op.create_index('uq_user_points_key', 'user_points', ['user_id', sa.literal_column('COALESCE(tournament_id, 0)'), 'reason', sa.literal_column('COALESCE(round_idx, 0)'), sa.literal_column("COALESCE(problem_slug, '')")], unique=True)
    op.create_table('tournament_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tournament_id', sa.Integer(), nullable=False),
    sa.Column('round_id', sa.Integer(), nullable=False),
    sa.Column('idx', sa.Integer(), nullable=False),
    sa.Column('members', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('winners', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('decided', sa.Boolean(), nullable=False),
    sa.Column('decided_by', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True),
    sa.Column('ranking', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('draw_seed', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['round_id'], ['tournament_rounds.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('round_id', 'idx', name='uq_group_idx')
    )
    op.create_index(op.f('ix_tournament_groups_round_id'), 'tournament_groups', ['round_id'], unique=False)
    op.create_index(op.f('ix_tournament_groups_tournament_id'), 'tournament_groups', ['tournament_id'], unique=False)
    op.add_column('tournament_players', sa.Column('status', sa.String(length=12), server_default='alive', nullable=False))
    op.add_column('tournament_players', sa.Column('eliminated_in_round', sa.Integer(), nullable=True))
    op.add_column('tournament_rounds', sa.Column('is_final', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('tournament_rounds', sa.Column('difficulty', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True))
    op.add_column('tournament_rounds', sa.Column('edited', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('tournaments', sa.Column('format', sqlmodel.sql.sqltypes.AutoString(length=14), server_default='aula', nullable=False))
    op.add_column('tournaments', sa.Column('gp_emitted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('show_in_leaderboard', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'show_in_leaderboard')
    op.drop_column('tournaments', 'gp_emitted_at')
    op.drop_column('tournaments', 'format')
    op.drop_column('tournament_rounds', 'edited')
    op.drop_column('tournament_rounds', 'difficulty')
    op.drop_column('tournament_rounds', 'is_final')
    op.drop_column('tournament_players', 'eliminated_in_round')
    op.drop_column('tournament_players', 'status')
    op.drop_index(op.f('ix_tournament_groups_tournament_id'), table_name='tournament_groups')
    op.drop_index(op.f('ix_tournament_groups_round_id'), table_name='tournament_groups')
    op.drop_table('tournament_groups')
    op.drop_index('uq_user_points_key', table_name='user_points')
    op.drop_index(op.f('ix_user_points_user_id'), table_name='user_points')
    op.drop_index('ix_user_points_created', table_name='user_points')
    op.drop_table('user_points')
