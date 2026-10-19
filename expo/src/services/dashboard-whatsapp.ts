import type { PricingItem } from '@/services/classio-data';

export type MessageLanguage = 'en' | 'es' | 'tr';
export type MessageTemplate = 'package' | 'package_offer' | 'confirm_today' | 'cancel_today';

const price = (value: number) => `${Math.round(value).toLocaleString('tr-TR')} ₺`;

export function dashboardMessage(name: string, language: MessageLanguage, template: MessageTemplate, status = 'almost_finished', time = '', pricing: PricingItem[] = []) {
  name = name.trim(); time = time.trim();
  if (template === 'confirm_today') {
    if (language === 'es') return `Hola ${name}! Solo para confirmar nuestra clase de hoy${time ? ` a las ${time}` : ''}. ¿Todo bien por tu lado?`;
    if (language === 'tr') return `Merhaba ${name}! Bugünkü dersimizi${time ? ` ${time} için` : ''} teyit etmek istiyorum. Sizin için uygun mu?`;
    return `Hi ${name}! Just confirming our lesson today${time ? ` at ${time}` : ''}. Is everything okay for you?`;
  }
  if (template === 'cancel_today') {
    if (language === 'es') return `Hola ${name}. Lo siento, pero necesito cancelar la clase de hoy. ¿Quieres reprogramarla?`;
    if (language === 'tr') return `Merhaba ${name}. Üzgünüm, bugünkü dersi iptal etmem gerekiyor. Yeniden planlayalım mı?`;
    return `Hi ${name}. I’m sorry, but I need to cancel today’s lesson. Would you like to reschedule?`;
  }
  if (template === 'package_offer') {
    const greeting = language === 'es' ? `Hola ${name}! Me gustaría compartir contigo las opciones actuales para continuar aprendiendo. Aquí tienes mis precios y paquetes:\n` : language === 'tr' ? `Merhaba ${name}! Derslere devam etmeniz için güncel seçeneklerimi paylaşmak istiyorum. Fiyatlarım ve paketlerim şöyle:\n` : `Hi ${name}! I’d love to share my current options for continuing your learning. Here are my lesson prices and packages:\n`;
    return `${greeting}\n${pricingBlock(language, pricing)}`;
  }
  const almost = status === 'finishing_soon' || /almost|soon|finish_soon/i.test(status);
  const statusText = language === 'es' ? (almost ? 'por terminar' : 'finalizado') : language === 'tr' ? (almost ? 'bitmek üzere' : 'tamamlandı') : (almost ? 'almost finished' : 'finished');
  const header = language === 'es' ? `Hola ${name}! Espero que estés bien.\nTu paquete actual está ${statusText}. Si quieres continuar, aquí están mis precios actuales:\n` : language === 'tr' ? `Merhaba ${name}, umarım iyisinizdir.\nMevcut paketiniz ${statusText}. Devam etmek isterseniz güncel fiyatlarım aşağıdadır:\n` : `Hi ${name}! Hope you’re doing well.\nYour current package is ${statusText}. If you’d like to continue, here are my current prices:\n`;
  return `${header}\n${pricingBlock(language, pricing)}`;
}

function pricingBlock(language: MessageLanguage, pricing: PricingItem[]) {
  const labels = language === 'es' ? ['📌 Las clases duran 50–60 minutos (1 hora).', '💻 Precios de clases online:', '🏫 Precios de clases presenciales:', '*La clase se paga el mismo día.', '📦 Paquetes online (prepago):', '*El pago debe hacerse antes de empezar. Puedes tomar clases con la frecuencia que quieras.', '📦 Paquetes presenciales (prepago):', '(No hay precio por hora online configurado)', '(No hay paquetes online)', '(No hay paquetes presenciales)'] : language === 'tr' ? ['Derslerim 50-60 dakika sürer (1 saat).', 'Çevrimiçi ders fiyatları:', 'Yüz yüze ders fiyatları:', '*Her ders aynı gün ödenmelidir.', 'Çevrimiçi Ders Ön ödemeli paketler:', '*Kursa başlamadan önce ödeme yapılmalıdır. Dersler istediğiniz sıklıkta alınabilir.', 'Yüz yüze Ders Ön ödemeli paketler:', '(Çevrimiçi saat ücreti ayarlanmamış)', '(Çevrimiçi paket yok)', '(Yüz yüze paket yok)'] : ['📌 Lessons are 50–60 minutes (1 hour).', '💻 Online lesson prices:', '🏫 In-person lesson prices:', '*Each lesson is paid on the same day.', '📦 Online prepaid packages:', '*Payment must be made before starting. Lessons can be taken as frequently as you want.', '📦 In-person prepaid packages:', '(No online hourly price set)', '(No online packages)', '(No in-person packages)'];
  const active = pricing.filter((item) => item.active);
  const hourly = (modality: PricingItem['modality']) => active.filter((item) => item.modality === modality && item.kind === 'hourly').sort((a, b) => a.sort_order - b.sort_order || Number(a.id || 0) - Number(b.id || 0))[0];
  const packages = (modality: PricingItem['modality']) => active.filter((item) => item.modality === modality && item.kind === 'package' && Number(item.hours) > 0).sort((a, b) => a.sort_order - b.sort_order || Number(b.hours) - Number(a.hours));
  const hourLine = (item: PricingItem) => `${language === 'tr' ? '1 saat' : language === 'es' ? '1 hora' : '1 hour'} → ${price(item.price)}\n`;
  const packageLine = (item: PricingItem) => `${item.hours} ${language === 'tr' ? 'saat' : language === 'es' ? 'horas' : 'hours'} → ${price(item.price)} (≈ ${price(item.price / Number(item.hours))} ${language === 'tr' ? 'ders/saati' : language === 'es' ? '/ hora' : '/ hour'})\n`;
  const onlineHourly = hourly('online'); const offlineHourly = hourly('offline'); const onlinePackages = packages('online'); const offlinePackages = packages('offline');
  let block = `${labels[0]}\n${labels[1]}\n`;
  block += onlineHourly?.price ? hourLine(onlineHourly) + `${labels[3]}\n` : `${labels[7]}\n`;
  block += `\n${labels[4]}\n`;
  block += onlinePackages.length ? onlinePackages.map(packageLine).join('') + `${labels[5]}\n` : `${labels[8]}\n`;
  block += `\n${labels[2]}\n`;
  if (offlineHourly?.price && language !== 'tr') block += hourLine(offlineHourly) + `${labels[3]}\n`;
  block += `\n${labels[6]}\n`;
  block += offlinePackages.length ? offlinePackages.map(packageLine).join('') + `${labels[5]}\n` : `${labels[9]}\n`;
  return `${block.trim()}\n`;
}
