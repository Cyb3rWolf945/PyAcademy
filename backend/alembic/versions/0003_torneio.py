"""Torneio "Formato Aula": torneios, agências, jogadores, rondas, pontuações, pistas, bónus, eventos e presença.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-15 10:19:26.775653
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('tournaments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('class_id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
    sa.Column('mode', sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
    sa.Column('join_code', sqlmodel.sql.sqltypes.AutoString(length=6), nullable=False),
    sa.Column('state', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('current_round', sa.Integer(), nullable=True),
    sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('lb_emitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['class_id'], ['school_classes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tournaments_class_id'), 'tournaments', ['class_id'], unique=False)
    op.create_index(op.f('ix_tournaments_join_code'), 'tournaments', ['join_code'], unique=True)
    op.create_index(op.f('ix_tournaments_teacher_id'), 'tournaments', ['teacher_id'], unique=False)
    op.create_table('presence',
    sa.Column('tournament_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seq', sa.BigInteger(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tournament_id', 'user_id'),
    prefixes=['UNLOGGED']
    )
    op.create_table('tournament_events',
    sa.Column('seq', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tournament_id', sa.Integer(), nullable=False),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('seq')
    )
    op.create_index('ix_tournament_events_tid_seq', 'tournament_events', ['tournament_id', 'seq'], unique=False)
    op.create_table('tournament_rounds',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tournament_id', sa.Integer(), nullable=False),
    sa.Column('idx', sa.Integer(), nullable=False),
    sa.Column('title', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('multiplier', sa.Float(), server_default='1', nullable=False),
    sa.Column('duration_s', sa.Integer(), nullable=False),
    sa.Column('is_boss', sa.Boolean(), nullable=False),
    sa.Column('problem_slugs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('state', sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('remaining_s', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tournament_id', 'idx', name='uq_round_idx')
    )
    op.create_index(op.f('ix_tournament_rounds_tournament_id'), 'tournament_rounds', ['tournament_id'], unique=False)
    op.create_table('tournament_teams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tournament_id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
    sa.Column('color_idx', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tournament_teams_tournament_id'), 'tournament_teams', ['tournament_id'], unique=False)
    op.create_index('uq_tournament_team_name', 'tournament_teams', ['tournament_id', sa.literal_column('lower(name)')], unique=True)
    op.create_table('tournament_bonus',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('round_id', sa.Integer(), nullable=False),
    sa.Column('participant_key', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
    sa.Column('points', sa.Float(), nullable=False),
    sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(length=12), nullable=False),
    sa.ForeignKeyConstraint(['round_id'], ['tournament_rounds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('round_id', 'kind', name='uq_bonus_round_kind')
    )
    op.create_table('tournament_hint_uses',
    sa.Column('round_id', sa.Integer(), nullable=False),
    sa.Column('problem_slug', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('n', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['round_id'], ['tournament_rounds.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('round_id', 'problem_slug', 'user_id', 'n')
    )
    op.create_table('tournament_players',
    sa.Column('tournament_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('team_id', sa.Integer(), nullable=True),
    sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['team_id'], ['tournament_teams.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('tournament_id', 'user_id')
    )
    op.create_index(op.f('ix_tournament_players_user_id'), 'tournament_players', ['user_id'], unique=False)
    op.create_table('tournament_solves',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tournament_id', sa.Integer(), nullable=False),
    sa.Column('round_id', sa.Integer(), nullable=False),
    sa.Column('problem_slug', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
    sa.Column('participant_key', sqlmodel.sql.sqltypes.AutoString(length=24), nullable=False),
    sa.Column('points', sa.Float(), nullable=False),
    sa.Column('hint_used', sa.Boolean(), nullable=False),
    sa.Column('submission_id', sa.Integer(), nullable=True),
    sa.Column('solved_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['round_id'], ['tournament_rounds.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tournament_id', 'round_id', 'problem_slug', 'participant_key', name='uq_solve_once')
    )
    op.create_index(op.f('ix_tournament_solves_tournament_id'), 'tournament_solves', ['tournament_id'], unique=False)
    op.create_table('tournament_submissions',
    sa.Column('submission_id', sa.Integer(), nullable=False),
    sa.Column('tournament_id', sa.Integer(), nullable=False),
    sa.Column('round_id', sa.Integer(), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['round_id'], ['tournament_rounds.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('submission_id')
    )
    op.create_index(op.f('ix_tournament_submissions_tournament_id'), 'tournament_submissions', ['tournament_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tournament_submissions_tournament_id'), table_name='tournament_submissions')
    op.drop_table('tournament_submissions')
    op.drop_index(op.f('ix_tournament_solves_tournament_id'), table_name='tournament_solves')
    op.drop_table('tournament_solves')
    op.drop_index(op.f('ix_tournament_players_user_id'), table_name='tournament_players')
    op.drop_table('tournament_players')
    op.drop_table('tournament_hint_uses')
    op.drop_table('tournament_bonus')
    op.drop_index('uq_tournament_team_name', table_name='tournament_teams')
    op.drop_index(op.f('ix_tournament_teams_tournament_id'), table_name='tournament_teams')
    op.drop_table('tournament_teams')
    op.drop_index(op.f('ix_tournament_rounds_tournament_id'), table_name='tournament_rounds')
    op.drop_table('tournament_rounds')
    op.drop_index('ix_tournament_events_tid_seq', table_name='tournament_events')
    op.drop_table('tournament_events')
    op.drop_table('presence')
    op.drop_index(op.f('ix_tournaments_teacher_id'), table_name='tournaments')
    op.drop_index(op.f('ix_tournaments_join_code'), table_name='tournaments')
    op.drop_index(op.f('ix_tournaments_class_id'), table_name='tournaments')
    op.drop_table('tournaments')
