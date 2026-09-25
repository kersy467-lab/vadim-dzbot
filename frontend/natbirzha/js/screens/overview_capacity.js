import { NatAPI } from '../api.js?v=20260925_energy_mechanic_v5_energy_mechanic_v5';

export async function updateBusinessCapacityCard(container) {
  const card = container.querySelector('#business-capacity-card');
  const summaryNode = card?.querySelector('#business-capacity-summary');
  const button = card?.querySelector('#expand-capacity-btn');
  if (!card || !summaryNode || !button) return;
  try {
    const summary = await NatAPI.getEmpireSummary();
    if (container.querySelector('#business-capacity-card') !== card) return;
    const slots = summary.slots || {};
    const expansion = summary.slot_expansion || {};
    summaryNode.textContent = `Занято ${Number(slots.used || 0)} / ${Number(slots.max || 10)} слотов.`;
    if (expansion.maxed) {
      summaryNode.textContent += ' Достигнут предел.';
      button.disabled = true;
      button.textContent = 'Лимит';
    } else if (expansion.is_upgrading) {
      const seconds = Number(expansion.remaining_seconds || 0);
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      summaryNode.textContent += ` Слот ${expansion.target_capacity} готовится: ${hours} ч ${String(minutes).padStart(2, '0')} мин.`;
      button.disabled = true;
      button.textContent = 'Идёт улучшение';
    } else {
      const price = Number(expansion.cost || 0).toLocaleString('ru-RU');
      summaryNode.textContent += ` Следующий слот: ${price} cash · ${expansion.duration_hours} ч.`;
      const enoughCash = Number(summary.cash || 0) >= Number(expansion.cost || 0);
      button.disabled = !enoughCash;
      button.textContent = enoughCash ? '＋ Добавить' : 'Не хватает cash';
    }
  } catch (error) {
    summaryNode.textContent = 'Не удалось загрузить состояние мощностей.';
    button.disabled = true;
  }
}
