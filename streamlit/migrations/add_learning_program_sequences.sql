-- Add progression-chain support for learning programs

alter table if exists learning_programs
    add column if not exists parent_program_id bigint references learning_programs(id) on delete set null,
    add column if not exists sequence_group_id text,
    add column if not exists sequence_order integer,
    add column if not exists prerequisite_summary text not null default '',
    add column if not exists entry_profile text not null default '',
    add column if not exists exit_profile text not null default '';

create index if not exists idx_learning_programs_sequence_group
    on learning_programs(sequence_group_id, sequence_order);

create index if not exists idx_learning_programs_parent_program
    on learning_programs(parent_program_id);
