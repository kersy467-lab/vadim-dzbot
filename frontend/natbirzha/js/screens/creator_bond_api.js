import { getAuthHeader } from '../api.js?v=20260925_sabotages_v2';

export async function declareCreatorBondBankruptcy(bondId) {
  const id = Number.parseInt(bondId, 10);
  if (!Number.isSafeInteger(id) || id <= 0) {
    throw new Error('Некорректный номер выпуска облигаций.');
  }

  const idempotencyKey = globalThis.crypto?.randomUUID?.()
    || `bond-default-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const response = await fetch(`/api/natbirzha/creator/bonds/${id}/bankrupt`, {
    method: 'POST',
    headers: {
      ...getAuthHeader(),
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail || data.message || 'Не удалось объявить банкротство выпуска.';
    throw new Error(Array.isArray(detail) ? detail.map(item => item.msg).join('; ') : String(detail));
  }
  return data;
}
