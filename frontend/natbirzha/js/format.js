export function formatNumber(val, decimals = 0) {
  const num = Number(val);
  if (!Number.isFinite(num)) {
    return (0).toLocaleString('ru-RU', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }
  return num.toLocaleString('ru-RU', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatCurrency(val, decimals = 2) {
  return `${formatNumber(val, decimals)} ₽`;
}
