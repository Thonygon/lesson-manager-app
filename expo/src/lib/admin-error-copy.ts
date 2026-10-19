import type { AppLanguage } from '@/providers/app-preferences';

const copy: Record<string, [string, string]> = {
  'The change was saved, but the audit record could not be written. Check the audit log before continuing.': ['El cambio se guardó, pero no se pudo registrar en auditoría. Revisa el historial antes de continuar.', 'Değişiklik kaydedildi ancak denetim kaydı yazılamadı. Devam etmeden önce denetim günlüğünü kontrol edin.'],
  'Admin access is required.': ['Se requiere acceso de administrador.', 'Yönetici erişimi gerekiyor.'],
  'Your session has expired.': ['Tu sesión ha vencido.', 'Oturumunuzun süresi doldu.'],
  'Your Classio session has expired.': ['Tu sesión de Classio ha vencido.', 'Classio oturumunuzun süresi doldu.'],
  'An account already uses this email.': ['Ya existe una cuenta con este correo.', 'Bu e-posta adresiyle zaten bir hesap var.'],
  'The selected plan is unavailable.': ['El plan seleccionado no está disponible.', 'Seçilen plan kullanılamıyor.'],
  'The account or plan is unavailable.': ['La cuenta o el plan no está disponible.', 'Hesap veya plan kullanılamıyor.'],
  'The user no longer exists.': ['La cuenta ya no existe.', 'Kullanıcı artık mevcut değil.'],
  'This staff role is already active.': ['Este rol del personal ya está activo.', 'Bu personel rolü zaten etkin.'],
  'That staff assignment is no longer active.': ['Esta asignación ya no está activa.', 'Bu personel ataması artık etkin değil.'],
  'Developer workspace requires an active staff role.': ['El espacio de Desarrollo requiere un rol de personal activo.', 'Geliştirici alanı için etkin bir personel rolü gerekiyor.'],
  'You cannot suspend your own admin account.': ['No puedes suspender tu propia cuenta de administrador.', 'Kendi yönetici hesabınızı askıya alamazsınız.'],
  'An admin cannot suspend their own account here.': ['No puedes suspender tu propia cuenta aquí.', 'Kendi hesabınızı burada askıya alamazsınız.'],
  'An admin cannot remove their own admin access here.': ['No puedes quitar tu propio acceso de administrador aquí.', 'Kendi yönetici erişiminizi burada kaldıramazsınız.'],
  'The default workspace must be enabled for this account.': ['El espacio predeterminado debe estar habilitado para esta cuenta.', 'Varsayılan çalışma alanı bu hesap için etkin olmalı.'],
  'Another admin changed this move. Refresh and try again.': ['Otro administrador cambió este recurso. Actualiza y vuelve a intentarlo.', 'Başka bir yönetici bu öğeyi değiştirdi. Yenileyip tekrar deneyin.'],
  'This move was already assigned to that account.': ['Este recurso ya fue asignado a esa cuenta.', 'Bu öğe zaten o hesaba atandı.'],
  'Only pending moves can be published.': ['Solo se pueden publicar recursos pendientes.', 'Yalnızca bekleyen öğeler yayınlanabilir.'],
  'Only unpublished moves can be edited.': ['Solo se pueden editar recursos sin publicar.', 'Yalnızca yayınlanmamış öğeler düzenlenebilir.'],
  'This move cannot be archived.': ['Este recurso no se puede archivar.', 'Bu öğe arşivlenemez.'],
  'This move cannot be assigned.': ['Este recurso no se puede asignar.', 'Bu öğe atanamaz.'],
  'The move or target account is unavailable.': ['El recurso o la cuenta de destino no está disponible.', 'Öğe veya hedef hesap kullanılamıyor.'],
  'Explorer move not found.': ['No se encontró el recurso de Explorer.', 'Explorer öğesi bulunamadı.'],
  'The edited resource is too large.': ['El recurso editado es demasiado grande.', 'Düzenlenen kaynak çok büyük.'],
  'Check the plan settings and USD price in cents.': ['Revisa la configuración y el precio del plan.', 'Plan ayarlarını ve fiyatı kontrol edin.'],
  'Check the plan features.': ['Revisa las funciones del plan.', 'Plan özelliklerini kontrol edin.'],
  'Choose a user, staff role, and reason.': ['Selecciona una cuenta, un rol y un motivo.', 'Bir kullanıcı, rol ve gerekçe seçin.'],
  'Choose a user and enter a reason.': ['Selecciona una cuenta e indica el motivo.', 'Bir kullanıcı seçip gerekçe girin.'],
  'Choose a move, target account, and reason.': ['Selecciona un recurso, una cuenta y un motivo.', 'Bir öğe, hedef hesap ve gerekçe seçin.'],
  'Choose a move, valid content, and reason.': ['Selecciona un recurso, contenido válido y un motivo.', 'Bir öğe, geçerli içerik ve gerekçe seçin.'],
  'Choose a move and enter a reason.': ['Selecciona un recurso e indica el motivo.', 'Bir öğe seçip gerekçe girin.'],
  'Choose an active assignment and enter a reason.': ['Selecciona una asignación activa e indica el motivo.', 'Etkin bir atama seçip gerekçe girin.'],
  'Enter an email, role, plan, and reason.': ['Indica correo, rol, plan y motivo.', 'E-posta, rol, plan ve gerekçe girin.'],
  'The Explorer preview could not be loaded.': ['No se pudo cargar la vista previa de Explorer.', 'Explorer önizlemesi yüklenemedi.'],
  'AI intelligence could not be loaded.': ['No se pudo cargar la información de IA.', 'YZ bilgileri yüklenemedi.'],
  'Access settings could not be saved.': ['No se pudo guardar la configuración de acceso.', 'Erişim ayarları kaydedilemedi.'],
};

export function localizeAdminError(message: string, language: AppLanguage): string {
  if (language === 'en') return message;
  const translated = copy[message]?.[language === 'es' ? 0 : 1];
  if (translated) return translated;
  return language === 'es' ? 'No se pudo completar la acción. Revisa los datos e inténtalo de nuevo.' : 'İşlem tamamlanamadı. Bilgileri kontrol edip yeniden deneyin.';
}
