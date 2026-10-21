import { createClient } from '@supabase/supabase-js';

const json = (body: unknown, status = 200) => Response.json(body, { status, headers: { 'Cache-Control': 'private, no-store', Vary: 'Authorization' } });
const clean = (value: unknown, max = 500) => String(value ?? '').trim().slice(0, max);
type Row = Record<string, unknown>;
function resourcePayload(move: Row, ownerId: string, ownerName: string, isPublic: boolean) {
  const meta = move.meta_json && typeof move.meta_json === 'object' && !Array.isArray(move.meta_json) ? move.meta_json as Row : {};
  const document = move.payload_json && typeof move.payload_json === 'object' && !Array.isArray(move.payload_json) ? move.payload_json as Row : {};
  const subject = clean(meta.subject || move.subject, 120), topic = clean(meta.topic || move.topic, 300), stage = clean(meta.learner_stage || move.learner_stage, 80), level = clean(meta.level_or_band || move.level_or_band, 80);
  const title = clean(document.title || move.title || topic, 300);
  const base = { user_id: ownerId, title, subject, topic, learner_stage: stage, is_public: isPublic, status: 'active', created_at: new Date().toISOString() };
  if (!title || !subject || !topic || !Object.keys(document).length) throw new Error('The Explorer move has incomplete resource data.');
  if (move.resource_type === 'lesson_plan') return { table: 'lesson_plans', payload: { ...base, level_or_band: level, lesson_purpose: clean(meta.lesson_purpose || 'introduce_concept'), plan_language: clean(document.plan_language || move.language || 'en'), student_material_language: clean(document.student_material_language || move.language || 'en'), source_type: 'ai', planner_mode: clean(meta.mode || 'ai'), plan_json: { ...document, ...(isPublic ? { _admin_only_image_controls: true } : {}) }, author_name: ownerName, subject_display: subject } };
  if (move.resource_type === 'worksheet') return { table: 'worksheets', payload: { ...base, level_or_band: level, worksheet_type: clean(meta.worksheet_type || document.worksheet_type || 'mixed_practice'), plan_language: clean(document.plan_language || move.language || 'en'), student_material_language: clean(document.student_material_language || move.language || 'en'), source_type: 'ai', worksheet_json: { ...document, ...(isPublic ? { _admin_only_image_controls: true } : {}) }, author_name: ownerName, subject_display: subject, updated_at: new Date().toISOString() } };
  if (move.resource_type === 'exam') {
    const exam = document.exam_data && typeof document.exam_data === 'object' && !Array.isArray(document.exam_data) ? document.exam_data as Row : document;
    const answers = document.answer_key && typeof document.answer_key === 'object' ? document.answer_key : {};
    return { table: 'quick_exams', payload: { ...base, title: clean(exam.title || title), level, exam_length: clean(meta.exam_length || 'medium'), exercise_types: Array.isArray(meta.exercise_types) ? meta.exercise_types : [], plan_language: clean(exam.plan_language || move.language || 'en'), student_material_language: clean(exam.student_material_language || move.language || 'en'), exam_data: { ...exam, ...(isPublic ? { _admin_only_image_controls: true } : {}) }, answer_key: answers, updated_at: new Date().toISOString() } };
  }
  throw new Error('This resource type cannot be published.');
}

export async function POST(request: Request) {
  const token = /^Bearer\s+(.+)$/i.exec(request.headers.get('authorization') || '')?.[1]?.trim();
  if (!token) return json({ error: 'Sign in to manage Classio.' }, 401);
  const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '';
  const publicKey = process.env.SUPABASE_ANON_KEY || process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY || '';
  const serverKey = process.env.SUPABASE_SECRET_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || '';
  if (!url || !publicKey || !serverKey) return json({ error: 'Admin actions are not configured.' }, 503);
  try {
    const publicClient = createClient(url, publicKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const { data: identity, error: identityError } = await publicClient.auth.getUser(token);
    if (identityError || !identity.user) return json({ error: 'Your session has expired.' }, 401);
    const server = createClient(url, serverKey, { auth: { persistSession: false, autoRefreshToken: false } });
    const actorId = identity.user.id;
    const { data: actor, error: actorError } = await server.from('profiles').select('role').eq('user_id', actorId).maybeSingle();
    if (actorError) throw actorError;
    if (actor?.role !== 'admin') return json({ error: 'Admin access is required.' }, 403);
    const input = await request.json().catch(() => null) as Record<string, unknown> | null;
    if (!input) return json({ error: 'Choose an admin action.' }, 400);
    const action = clean(input.action, 40), userId = clean(input.userId, 100), reason = clean(input.reason, 800);
    // A durable intent record is required before any privileged write. If a later
    // step fails, this record still identifies the attempted action for recovery.
    const { error: intentError } = await server.from('admin_overrides').insert({ user_id: userId || actorId, override_type: 'admin_action_attempt', reason: `${action}: ${reason}`, created_by: actorId });
    if (intentError) throw intentError;
    const audit = async (target: string, type: string, note: string) => {
      const { error } = await server.from('admin_overrides').insert({ user_id: target || actorId, override_type: type, reason: note, created_by: actorId });
      if (error) console.error('Admin audit write failed', { type, message: error.message });
      return !error;
    };
    if (action === 'account_create') {
      const email = clean(input.email, 254).toLowerCase(), name = clean(input.name, 160), role = clean(input.role, 30), planId = clean(input.planId, 80);
      const canTeach = typeof input.canTeach === 'boolean' ? input.canTeach : role !== 'student';
      const canStudy = typeof input.canStudy === 'boolean' ? input.canStudy : role === 'student';
      const staffRole = clean(input.staffRole, 40), activeMode = clean(input.activeMode || (canTeach ? 'teacher' : 'student'), 40);
      const accountStatus = clean(input.accountStatus || 'active', 20), subscriptionStatus = clean(input.subscriptionStatus || (planId === 'free' ? 'free' : 'active'), 20);
      const notes = clean(input.notes, 1000);
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || !['teacher', 'student', 'school_admin', 'admin'].includes(role) || !planId || !reason) return json({ error: 'Enter an email, role, plan, and reason.' }, 400);
      if (!['', 'developer', 'data_scientist'].includes(staffRole) || !['active', 'suspended'].includes(accountStatus) || !['free', 'active', 'trialing', 'past_due', 'canceled', 'expired'].includes(subscriptionStatus)) return json({ error: 'Choose valid account access settings.' }, 400);
      if (!((activeMode === 'teacher' && canTeach) || (activeMode === 'student' && canStudy) || (activeMode === 'admin' && role === 'admin') || (activeMode === 'developer_workspace' && (role === 'admin' || Boolean(staffRole))))) return json({ error: 'The default workspace must be enabled for this account.' }, 400);
      const { data: plan, error: planError } = await server.from('plans').select('id,active').eq('id', planId).maybeSingle();
      if (planError) throw planError;
      if (!plan || plan.active === false) return json({ error: 'The selected plan is unavailable.' }, 400);
      const { data: existing, error: existingError } = await server.from('profiles').select('user_id').eq('email', email).maybeSingle();
      if (existingError) throw existingError;
      if (existing) return json({ error: 'An account already uses this email.' }, 409);
      const { data: invitation, error: invitationError } = await server.auth.admin.inviteUserByEmail(email);
      if (invitationError || !invitation.user) throw invitationError ?? new Error('The invitation could not be created.');
      const userId = invitation.user.id;
      const { error: profileError } = await server.from('profiles').upsert({ user_id: userId, email, display_name: name || email.split('@')[0], preferred_ui_language: 'en', timezone: 'Europe/Istanbul', default_lesson_duration: 45, role, primary_role: canTeach ? 'teacher' : 'student', can_teach: canTeach, can_study: canStudy, last_active_mode: activeMode, current_plan: planId, subscription_status: subscriptionStatus, account_status: accountStatus, admin_notes: notes, primary_subjects: [], teaching_stages: [], teaching_languages: [], login_count: 0, active_student_count: 0, onboarding_completed: false }, { onConflict: 'user_id' });
      if (profileError) throw profileError;
      const { error: subscriptionError } = await server.from('user_subscriptions').upsert({ user_id: userId, plan_id: planId, subscription_status: subscriptionStatus, manual_override: true }, { onConflict: 'user_id' });
      if (subscriptionError) throw subscriptionError;
      if (staffRole) {
        const { error: staffError } = await server.from('user_staff_roles').insert({ user_id: userId, role_key: staffRole, is_active: true, assigned_by: actorId, assigned_at: new Date().toISOString(), assignment_reason: reason, metadata: {} });
        if (staffError) throw staffError;
      }
      return json({ ok: true, userId, audited: await audit(userId, 'account_create', `${reason}; role=${role}; staff=${staffRole || 'none'}; plan=${planId}; status=${subscriptionStatus}`) });
    }
    if (action === 'user_update') {
      const email = clean(input.email, 254).toLowerCase(), name = clean(input.name, 160), role = clean(input.role, 30), planId = clean(input.planId, 80);
      const canTeach = input.canTeach, canStudy = input.canStudy;
      const activeMode = clean(input.activeMode, 40), accountStatus = clean(input.accountStatus, 20), subscriptionStatus = clean(input.subscriptionStatus, 20), notes = clean(input.notes, 1000);
      if (!userId || !reason || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || !['teacher', 'student', 'school_admin', 'admin'].includes(role) || !planId || typeof canTeach !== 'boolean' || typeof canStudy !== 'boolean' || !['active', 'suspended'].includes(accountStatus) || !['free', 'active', 'trialing', 'past_due', 'canceled', 'expired'].includes(subscriptionStatus)) return json({ error: 'Choose valid account access settings.' }, 400);
      if (!((activeMode === 'teacher' && canTeach) || (activeMode === 'student' && canStudy) || (activeMode === 'admin' && role === 'admin') || activeMode === 'developer_workspace')) return json({ error: 'The default workspace must be enabled for this account.' }, 400);
      if (userId === actorId && (role !== 'admin' || accountStatus !== 'active')) return json({ error: 'An admin cannot remove or suspend their own admin access.' }, 400);
      const [{ data: target, error: targetError }, { data: plan, error: planError }, { data: duplicate, error: duplicateError }] = await Promise.all([
        server.from('profiles').select('user_id,email').eq('user_id', userId).maybeSingle(),
        server.from('plans').select('id').eq('id', planId).maybeSingle(),
        server.from('profiles').select('user_id').eq('email', email).neq('user_id', userId).limit(1),
      ]);
      if (targetError || planError || duplicateError) throw targetError || planError || duplicateError;
      if (!target || !plan) return json({ error: 'The account or plan is unavailable.' }, 404);
      if (duplicate?.length) return json({ error: 'An account already uses this email.' }, 409);
      if (activeMode === 'developer_workspace' && role !== 'admin') {
        const { data: staff, error: staffError } = await server.from('user_staff_roles').select('id').eq('user_id', userId).eq('is_active', true).in('role_key', ['developer', 'data_scientist']).limit(1);
        if (staffError) throw staffError;
        if (!staff?.length) return json({ error: 'Developer workspace requires an active staff role.' }, 400);
      }
      const previousEmail = clean(target.email, 254).toLowerCase();
      if (email !== previousEmail) {
        const { error: authError } = await server.auth.admin.updateUserById(userId, { email, email_confirm: true });
        if (authError) throw authError;
      }
      const { error: profileError } = await server.from('profiles').update({ email, display_name: name, role, primary_role: canTeach ? 'teacher' : 'student', can_teach: canTeach, can_study: canStudy, last_active_mode: activeMode, account_status: accountStatus, current_plan: planId, subscription_status: subscriptionStatus, admin_notes: notes }).eq('user_id', userId);
      if (profileError) {
        if (email !== previousEmail && previousEmail) await server.auth.admin.updateUserById(userId, { email: previousEmail, email_confirm: true });
        throw profileError;
      }
      const { error: subscriptionError } = await server.from('user_subscriptions').upsert({ user_id: userId, plan_id: planId, subscription_status: subscriptionStatus, manual_override: true, updated_at: new Date().toISOString() }, { onConflict: 'user_id' });
      if (subscriptionError) throw subscriptionError;
      return json({ ok: true, audited: await audit(userId, 'user_row_update', reason) });
    }
    if (action === 'staff_assign') {
      const role = clean(input.role, 40);
      if (!userId || !['developer', 'data_scientist'].includes(role) || !reason) return json({ error: 'Choose a user, staff role, and reason.' }, 400);
      const [{ data: target, error: targetError }, { data: existing, error: existingError }] = await Promise.all([
        server.from('profiles').select('user_id').eq('user_id', userId).maybeSingle(),
        server.from('user_staff_roles').select('id').eq('user_id', userId).eq('role_key', role).eq('is_active', true).limit(1),
      ]);
      if (targetError || existingError) throw targetError || existingError;
      if (!target) return json({ error: 'The user no longer exists.' }, 404);
      if (existing?.length) return json({ error: 'This staff role is already active.' }, 409);
      const { data, error } = await server.rpc('classio_admin_change_staff', { p_actor_id: actorId, p_action: 'assign', p_target_id: userId, p_role: role, p_assignment_id: null, p_reason: reason });
      if (error) throw error;
      if (!data?.assignment_id) throw new Error('Staff assignment could not be confirmed.');
      return json({ ok: true, audited: true });
    }
    if (action === 'staff_revoke') {
      const id = Number(input.assignmentId);
      if (!Number.isInteger(id) || id < 1 || !reason) return json({ error: 'Choose an active assignment and enter a reason.' }, 400);
      const { data: assignment, error: lookupError } = await server.from('user_staff_roles').select('id,user_id,role_key').eq('id', id).eq('is_active', true).maybeSingle();
      if (lookupError) throw lookupError;
      if (!assignment) return json({ error: 'That staff assignment is no longer active.' }, 404);
      const { data, error } = await server.rpc('classio_admin_change_staff', { p_actor_id: actorId, p_action: 'revoke', p_target_id: assignment.user_id, p_role: assignment.role_key, p_assignment_id: id, p_reason: reason });
      if (error) throw error;
      if (data?.assignment_id !== id) throw new Error('Staff revocation could not be confirmed.');
      return json({ ok: true, audited: true });
    }
    if (action === 'account_status' || action === 'reset_usage') {
      if (!userId || !reason) return json({ error: 'Choose a user and enter a reason.' }, 400);
      if (userId === actorId && action === 'account_status') return json({ error: 'You cannot suspend your own admin account.' }, 400);
      const { data: target, error: targetError } = await server.from('profiles').select('user_id').eq('user_id', userId).maybeSingle();
      if (targetError) throw targetError;
      if (!target) return json({ error: 'The user no longer exists.' }, 404);
      if (action === 'account_status') {
        const status = clean(input.status, 20);
        if (!['active', 'suspended'].includes(status)) return json({ error: 'Choose an allowed account status.' }, 400);
        const { data, error } = await server.rpc('classio_admin_account_control', { p_actor_id: actorId, p_target_id: userId, p_action: 'account_status', p_status: status, p_reason: reason });
        if (error) throw error;
        if (data !== true) throw new Error('Account status change could not be confirmed.');
        return json({ ok: true, audited: true });
      }
      const { data, error } = await server.rpc('classio_admin_account_control', { p_actor_id: actorId, p_target_id: userId, p_action: 'reset_usage', p_status: null, p_reason: reason });
      if (error) throw error;
      if (data !== true) throw new Error('Usage reset could not be confirmed.');
      return json({ ok: true, audited: true });
    }
    if (action === 'plan_save') {
      const plan = input.plan && typeof input.plan === 'object' && !Array.isArray(input.plan) ? input.plan as Record<string, unknown> : null;
      const id = clean(plan?.id, 80), name = clean(plan?.name, 160), interval = clean(plan?.billing_interval, 20);
      const price = plan?.price === null ? null : Number(plan?.price);
      if (!id || !name || !['month', 'year', 'lifetime', 'custom'].includes(interval) || typeof plan?.active !== 'boolean' || (price !== null && (!Number.isInteger(price) || price < 0 || price > 100000000))) return json({ error: 'Check the plan settings and USD price in cents.' }, 400);
      const rawLimits = plan?.limits_json && typeof plan.limits_json === 'object' && !Array.isArray(plan.limits_json) ? plan.limits_json as Record<string, unknown> : {};
      const safeLimits: Record<string, number> = {};
      for (const key of ['ai_generations', 'pdf_exports', 'word_exports', 'students_count', 'classes_count']) { const value = Number(rawLimits[key] ?? (key === 'ai_generations' ? 10 : 0)); if (!Number.isInteger(value) || value < 0 || value > 10000000) return json({ error: `Check ${key}.` }, 400); safeLimits[key] = value; }
      const features = plan?.features_json && typeof plan.features_json === 'object' && !Array.isArray(plan.features_json) ? plan.features_json as Record<string, unknown> : {};
      if (Object.keys(features).length > 100 || Object.entries(features).some(([key, value]) => key.length > 100 || !(typeof value === 'boolean' || Array.isArray(value)))) return json({ error: 'Check the plan features.' }, 400);
      const { error } = await server.from('plans').upsert({ id, name, price, billing_interval: interval, active: plan.active, features_json: features, limits_json: safeLimits }, { onConflict: 'id' });
      if (error) throw error;
      return json({ ok: true, audited: await audit('', 'plan_update', `${id}: ${reason || 'Updated plan'}`) });
    }
    if (action === 'explorer_edit') {
      const id = Number(input.moveId), document = input.document;
      if (!Number.isInteger(id) || id < 1 || !reason || !document || typeof document !== 'object' || Array.isArray(document)) return json({ error: 'Choose a move, valid content, and reason.' }, 400);
      if (JSON.stringify(document).length > 250000) return json({ error: 'The edited resource is too large.' }, 400);
      const { data: move, error: lookupError } = await server.from('explorer_moves').select('id,status,resource_type,meta_json,title,subject,topic,updated_at').eq('id', id).maybeSingle();
      if (lookupError) throw lookupError;
      if (!move || !['pending', 'solved'].includes(move.status)) return json({ error: 'Only unpublished moves can be edited.' }, 409);
      const candidate = { ...move, payload_json: document };
      resourcePayload(candidate as Row, actorId, 'Classio', false);
      const editedTitle = clean((document as Row).title || ((document as Row).exam_data as Row | undefined)?.title || move.title, 300);
      const { data: updated, error } = await server.from('explorer_moves').update({ payload_json: document, title: editedTitle, updated_at: new Date().toISOString() }).eq('id', id).eq('status', move.status).eq('updated_at', move.updated_at).select('id');
      if (error) throw error;
      if (!updated?.length) return json({ error: 'Another admin changed this move. Refresh and try again.' }, 409);
      return json({ ok: true, audited: await audit(actorId, 'explorer_move_edit', `${id}: ${reason}`) });
    }
    if (action === 'explorer_publish' || action === 'explorer_assign') {
      const id = Number(input.moveId), targetId = action === 'explorer_assign' ? clean(input.userId, 100) : actorId;
      if (!Number.isInteger(id) || id < 1 || !targetId || !reason) return json({ error: 'Choose a move, target account, and reason.' }, 400);
      const [{ data: move, error: moveError }, { data: owner, error: ownerError }] = await Promise.all([
        server.from('explorer_moves').select('*').eq('id', id).maybeSingle(),
        server.from('profiles').select('user_id,display_name,email').eq('user_id', targetId).maybeSingle(),
      ]);
      if (moveError || ownerError) throw moveError || ownerError;
      if (!move || !owner) return json({ error: 'The move or target account is unavailable.' }, 404);
      if (action === 'explorer_publish' && move.status !== 'pending') return json({ error: 'Only pending moves can be published.' }, 409);
      if (action === 'explorer_assign' && !['pending', 'solved'].includes(move.status)) return json({ error: 'This move cannot be assigned.' }, 409);
      const previousNotes = (() => { try { return JSON.parse(String(move.admin_notes || '{}')) as Row; } catch { return {}; } })();
      const assignments = Array.isArray(previousNotes.assignments) ? previousNotes.assignments as Row[] : [];
      if (action === 'explorer_assign' && assignments.some((row) => clean(row.target_user_id) === targetId)) return json({ error: 'This move was already assigned to that account.' }, 409);
      const resource = resourcePayload(move as Row, targetId, clean(owner.display_name || owner.email || 'Classio'), action === 'explorer_publish');
      const { data: inserted, error: insertError } = await server.from(resource.table).insert(resource.payload as never).select('id').single();
      if (insertError || !inserted) throw insertError ?? new Error('Resource save failed.');
      const now = new Date().toISOString();
      const statusPayload = action === 'explorer_publish'
        ? { status: 'published', published_table: resource.table, published_record_id: inserted.id, published_at: now, updated_at: now, admin_notes: reason }
        : { status: 'solved', updated_at: now, admin_notes: JSON.stringify({ ...previousNotes, assignments: [...assignments, { target_user_id: targetId, target_owner_name: clean(owner.display_name || owner.email), assigned_by_admin: actorId, assigned_at: now, record_id: inserted.id }] }) };
      const update = await server.from('explorer_moves').update(statusPayload).eq('id', id).eq('status', move.status).select('id');
      if (update.error || !update.data?.length) {
        await server.from(resource.table).delete().eq('id', inserted.id);
        if (update.error) throw update.error;
        return json({ error: 'Another admin changed this move. Refresh and try again.' }, 409);
      }
      return json({ ok: true, recordId: inserted.id, audited: await audit(targetId, action === 'explorer_publish' ? 'explorer_move_publish' : 'explorer_move_assign', `${id}: ${reason}`) });
    }
    if (action === 'explorer_archive') {
      const id = Number(input.moveId);
      if (!Number.isInteger(id) || id < 1 || !reason) return json({ error: 'Choose a move and enter a reason.' }, 400);
      const { data: move, error: lookupError } = await server.from('explorer_moves').select('id,status,published_table,published_record_id').eq('id', id).maybeSingle();
      if (lookupError) throw lookupError;
      if (!move || !['pending', 'published', 'solved'].includes(move.status)) return json({ error: 'This move cannot be archived.' }, 409);
      const hadPublishedResource = move.status === 'published' && Boolean(move.published_record_id);
      if (hadPublishedResource) {
        if (!['lesson_plans', 'worksheets', 'quick_exams'].includes(String(move.published_table))) return json({ error: 'The published resource location is invalid.' }, 400);
        const { error: resourceError } = await server.from(String(move.published_table)).update({ status: 'archived', is_public: false }).eq('id', move.published_record_id);
        if (resourceError) throw resourceError;
      }
      const { data: archived, error } = await server.from('explorer_moves').update({ status: 'archived', admin_notes: reason, updated_at: new Date().toISOString() }).eq('id', id).eq('status', move.status).select('id');
      if (error || !archived?.length) {
        if (hadPublishedResource) await server.from(String(move.published_table)).update({ status: 'active', is_public: true }).eq('id', move.published_record_id);
        if (error) throw error;
        return json({ error: 'Another admin changed this move. Refresh and try again.' }, 409);
      }
      return json({ ok: true, audited: await audit('', 'explorer_move_archive', `${id}: ${reason}`) });
    }
    return json({ error: 'This admin action is not supported.' }, 400);
  } catch (error) { console.error('Admin action failed', error); return json({ error: 'The admin action could not be completed.' }, 502); }
}
