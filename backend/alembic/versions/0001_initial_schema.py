"""Migração inicial: todas as tabelas da fase 1.

Revision ID: 0001
Revises: 
Create Date: 2026-11-14 23:31:23.209423
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    
    op.create_table('login_attempts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('ip', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_login_attempts_at'), 'login_attempts', ['at'], unique=False)
    op.create_index(op.f('ix_login_attempts_username'), 'login_attempts', ['username'], unique=False)
    op.create_table('problems',
    sa.Column('slug', sqlmodel.sql.sqltypes.AutoString(length=80), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('estado', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('bloco', sqlmodel.sql.sqltypes.AutoString(length=4), nullable=False),
    sa.Column('tipo', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('slug')
    )
    op.create_index(op.f('ix_problems_bloco'), 'problems', ['bloco'], unique=False)
    op.create_index(op.f('ix_problems_estado'), 'problems', ['estado'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('display_name', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
    sa.Column('password_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('role', sa.Enum('teacher', 'student', name='role'), nullable=False),
    sa.Column('locale', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('preferred_theme', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
    sa.Column('class_id', sa.Integer(), nullable=True),
    sa.Column('must_change_password', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_actor_id'), 'audit_log', ['actor_id'], unique=False)
    op.create_table('school_classes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=60), nullable=False),
    sa.Column('join_code', sqlmodel.sql.sqltypes.AutoString(length=6), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_school_classes_join_code'), 'school_classes', ['join_code'], unique=True)
    # FK circular users <-> school_classes: criada depois das duas tabelas existirem
    op.create_foreign_key('fk_users_class_id', 'users', 'school_classes', ['class_id'], ['id'], ondelete='SET NULL')
    op.create_table('sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('csrf_token', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sessions_token_hash'), 'sessions', ['token_hash'], unique=True)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)


def downgrade() -> None:
    
    op.drop_constraint('fk_users_class_id', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_token_hash'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_index(op.f('ix_school_classes_join_code'), table_name='school_classes')
    op.drop_table('school_classes')
    op.drop_index(op.f('ix_audit_log_actor_id'), table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_problems_estado'), table_name='problems')
    op.drop_index(op.f('ix_problems_bloco'), table_name='problems')
    op.drop_table('problems')
    op.drop_index(op.f('ix_login_attempts_username'), table_name='login_attempts')
    op.drop_index(op.f('ix_login_attempts_at'), table_name='login_attempts')
    op.drop_table('login_attempts')
    sa.Enum(name='role').drop(op.get_bind(), checkfirst=True)
