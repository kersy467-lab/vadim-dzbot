export const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[ch]));
export const number = (value) => Number(value || 0).toLocaleString('ru-RU');

export function timeLeft(value) {
  if (!value) return 'нет таймера';
  const seconds = Math.max(0, Math.floor((new Date(value).getTime() - Date.now()) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return seconds <= 0 ? 'завершено' : `${hours} ч ${minutes} мин`;
}

export function unavailableReason(reason) {
  return {
    company_level: 'Нужен более высокий уровень компании',
    prerequisite: 'Сначала захватите предыдущую корпорацию',
    force_composition: 'Состав армии не соответствует требованиям этого тира',
    insufficient_force_composition: 'Состав армии не соответствует требованиям этого тира',
    already_conquered: 'Территория уже захвачена',
    cooldown: 'Повторная атака пока на кулдауне',
  }[reason] || 'Цель сейчас недоступна';
}

export function armyRequirementText(requirements = {}, missing = {}) {
  const labels = {
    ground_total: 'Наземные войска',
    border_guards: 'Пограничники',
    tanks: 'Бронетехника',
    drones: 'БПЛА',
    aircraft: 'Авиация',
    air_defense: 'ПВО',
  };
  return Object.entries(requirements).map(([unit, required]) => {
    const gap = missing?.[unit];
    return `${labels[unit] || unit}: ${number(required)}${gap ? ` (не хватает ${number(gap.missing)})` : ''}`;
  }).join(' · ');
}
