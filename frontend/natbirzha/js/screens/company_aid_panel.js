import { NatAPI } from '../api.js?v=20261009_perf_tuning_v1';
import { ITEMS, getItemInfo } from '../items.js?v=20261009_luxury_ui_v2';
import { formatNumber } from '../format.js';

const CASH_LIMIT = 100_000;
const classes = {
  card: 'glass-card rounded-2xl p-4 space-y-3',
  button: 'rounded-xl px-4 py-2.5 font-bold disabled:opacity-50',
  input: 'min-w-0 w-full rounded-xl border border-slate-300/30 px-3 py-2.5 bg-transparent',
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = String(text);
  return node;
}

function button(text, className = 'bg-indigo-600 text-white') {
  const node = el('button', `${classes.button} ${className}`, text);
  node.type = 'button';
  return node;
}

function number(value, digits = 2) {
  return formatNumber(Number(value) || 0, digits);
}

function itemLabel(itemId) {
  const item = getItemInfo(itemId);
  return item.name;
}

function remainingRequest(request) {
  if (request.kind === 'cash') {
    return Math.max(0, Number(request.amount_cash) - Number(request.fulfilled_value_cash || 0));
  }
  return Math.max(0, Number(request.item_quantity) - Number(request.fulfilled_quantity || 0));
}

function addField(parent, labelText, control) {
  const label = el('label', 'block space-y-1.5 text-sm');
  label.append(el('span', 'block text-xs font-bold text-slate-500', labelText), control);
  parent.append(label);
  return control;
}

function setBusy(buttonNode, busy, busyText, idleText) {
  buttonNode.disabled = busy;
  buttonNode.textContent = busy ? busyText : idleText;
}

export async function renderCompanyAidPanel(container, showToast, onRefresh) {
  let active = true;
  const toast = (message, type = 'success') => showToast?.(message, type);
  const root = el('div', 'max-w-md mx-auto p-4 pb-24 space-y-4');
  container.replaceChildren(root);

  const header = el('header', 'space-y-1');
  header.append(
    el('h2', 'text-xl font-black', 'Помощь компаниям'),
    el('p', 'text-xs text-slate-500', 'Поддержите небольшую компанию деньгами или товарами со своего склада.'),
  );
  root.append(header);

  const intro = el('div', `${classes.card} text-sm`);
  intro.append(el('p', 'font-bold', 'Помощь добровольная и без долгов.'),
    el('p', 'text-xs text-slate-500', 'Получатель может принять помощь через свою заявку. Недельный лимит — 100 000 cash по базовым ценам каталога.'),
    el('p', 'text-xs text-slate-500', 'Один наставник может помогать максимум двум разным компаниям за любые 7 дней.')); 
  root.append(intro);

  const summaryCard = el('section', `${classes.card} border border-amber-300/30`);
  const summaryBody = el('div', 'space-y-2');
  summaryBody.append(el('div', 'text-sm text-slate-500', 'Загружаем репутацию наставника…'));
  summaryCard.append(summaryBody);
  root.append(summaryCard);

  const myRequestSection = el('section', 'space-y-2');
  myRequestSection.append(el('h3', 'font-bold', 'Моя заявка'));
  const myRequestBody = el('div', 'space-y-2');
  myRequestSection.append(myRequestBody);
  root.append(myRequestSection);

  const createCard = el('section', `${classes.card}`);
  createCard.append(el('h3', 'font-bold', 'Попросить поддержку'));
  createCard.append(el('p', 'text-xs text-slate-500', 'Укажите нужную сумму или товар. В заявке на деньги напишите, на что пойдёт помощь: например, на оплату расходов и запуск заводов.'));
  const form = el('form', 'space-y-3');
  const kindSelect = el('select', classes.input);
  for (const [value, label] of [['cash', 'Деньги'], ['item', 'Товар со склада']]) {
    const option = el('option', '', label);
    option.value = value;
    kindSelect.append(option);
  }
  addField(form, 'Что нужно', kindSelect);

  const cashInput = el('input', classes.input);
  cashInput.type = 'number'; cashInput.min = '1'; cashInput.max = String(CASH_LIMIT); cashInput.step = '1'; cashInput.placeholder = 'Например, 25000';
  const cashField = el('div', 'space-y-1.5');
  addField(cashField, 'Сумма cash (до 100 000)', cashInput);
  form.append(cashField);

  const itemSelect = el('select', classes.input);
  for (const itemId of Object.keys(ITEMS).sort((a, b) => itemLabel(a).localeCompare(itemLabel(b), 'ru'))) {
    const option = el('option', '', `${itemLabel(itemId)} · ${ITEMS[itemId].unit}`);
    option.value = itemId;
    itemSelect.append(option);
  }
  const qtyInput = el('input', classes.input);
  qtyInput.type = 'number'; qtyInput.min = '0.001'; qtyInput.step = '0.001'; qtyInput.placeholder = 'Количество';
  const itemFields = el('div', 'space-y-3');
  addField(itemFields, 'Товар', itemSelect);
  addField(itemFields, 'Количество', qtyInput);
  form.append(itemFields);

  const messageInput = el('textarea', classes.input);
  messageInput.rows = 3; messageInput.maxLength = 500; messageInput.placeholder = 'Коротко объясните, зачем нужна помощь';
  addField(form, 'Комментарий для компаний', messageInput);
  const createButton = button('Опубликовать заявку', 'bg-pink-600 text-white');
  createButton.type = 'submit';
  form.append(createButton);
  createCard.append(form);
  root.append(createCard);

  const requestsSection = el('section', 'space-y-2');
  requestsSection.append(el('h3', 'font-bold', 'Заявки компаний'));
  const requestsBody = el('div', 'space-y-2');
  requestsSection.append(requestsBody);
  root.append(requestsSection);

  async function refreshAll() {
    await Promise.resolve(onRefresh?.()).catch(() => {});
    await refreshData();
  }

  function updateCreateFields() {
    const isCash = kindSelect.value === 'cash';
    cashField.hidden = !isCash;
    itemFields.hidden = isCash;
    messageInput.required = isCash;
    messageInput.placeholder = isCash
      ? 'Например: помощь на оплату расходов запуска завода'
      : 'Коротко объясните, зачем нужен товар';
  }
  kindSelect.addEventListener('change', updateCreateFields);
  updateCreateFields();

  function requestSummary(request) {
    const valueLeft = remainingRequest(request);
    if (request.kind === 'cash') return `Осталось: ${number(valueLeft, 0)} cash`;
    const item = getItemInfo(request.item_id);
    return `${itemLabel(request.item_id)} · осталось ${number(valueLeft, 3)} ${item.unit}`;
  }

  function renderSummary(summary) {
    summaryBody.replaceChildren();
    summaryBody.append(
      el('div', 'text-xs font-bold uppercase tracking-wide text-slate-500', 'Репутация помощи'),
      el('div', 'text-lg font-black text-amber-500', summary.mentor_title || 'Будущий наставник'),
      el('div', 'text-sm', `Поддержано компаний: ${number(summary.supported_companies, 0)} · всего ${number(summary.total_aid_value_cash, 2)} cash`),
      el('div', 'text-xs text-slate-500', `За последние 7 дней помогли компаниям: ${number(summary.current_week_supported_count, 0)}/${number(summary.max_supported_companies_per_week, 2)}`),
      el('div', 'text-xs text-slate-500', `Можно получить ещё ${number(summary.recipient_week_remaining_cash, 2)} cash помощи за последние 7 дней.`),
      el('div', 'text-[10px] text-slate-500', 'Звание косметическое: оно не даёт cash и не меняет производство.'),
    );
  }

  function renderMine(request) {
    myRequestBody.replaceChildren();
    if (!request) {
      myRequestBody.append(el('div', `${classes.card} text-sm text-slate-500`, 'Открытой заявки нет. Получать помощь могут компании до 10 уровня.'));
      createButton.disabled = false;
      return;
    }
    const card = el('article', classes.card);
    card.append(el('div', 'font-bold', request.kind === 'cash' ? `Нужны деньги · ${number(request.amount_cash, 0)} cash` : `Нужен товар · ${itemLabel(request.item_id)}`));
    card.append(el('div', 'text-xs text-slate-500', requestSummary(request)));
    if (request.message) card.append(el('p', 'text-sm whitespace-pre-wrap', request.message));
    const cancel = button('Отменить заявку', 'border border-rose-400/50 text-rose-600');
    cancel.addEventListener('click', async () => {
      setBusy(cancel, true, 'Отменяем…', 'Отменить заявку');
      try {
        await NatAPI.cancelAidRequest(Number(request.id));
        toast('Заявка отменена');
        await refreshAll();
      } catch (error) {
        toast(error?.message || 'Не удалось отменить заявку', 'error');
        setBusy(cancel, false, 'Отменяем…', 'Отменить заявку');
      }
    });
    card.append(cancel);
    myRequestBody.append(card);
    createButton.disabled = true;
  }

  function renderRequests(requests) {
    requestsBody.replaceChildren();
    if (!requests.length) {
      requestsBody.append(el('div', `${classes.card} text-sm text-slate-500`, 'Открытых заявок пока нет.'));
      return;
    }
    for (const request of requests) {
      const card = el('article', classes.card);
      const companyLabel = request.company_name || request.company_ticker || `Компания #${request.company_id}`;
      const title = request.kind === 'cash'
        ? `Нужны деньги · ${number(request.amount_cash, 0)} cash`
        : `Нужен товар · ${itemLabel(request.item_id)}`;
      card.append(el('div', 'flex items-start justify-between gap-2', ''));
      const heading = card.lastElementChild;
      heading.append(el('b', 'text-sm', companyLabel), el('span', 'text-xs text-slate-500', title));
      card.append(el('div', 'text-xs text-slate-500', requestSummary(request)));
      if (request.message) card.append(el('p', 'text-sm whitespace-pre-wrap', request.message));

      const transferForm = el('form', 'space-y-2 border-t border-slate-300/20 pt-3');
      const quantity = el('input', classes.input);
      quantity.type = 'number'; quantity.min = request.kind === 'cash' ? '1' : '0.001';
      quantity.step = request.kind === 'cash' ? '1' : '0.001';
      quantity.max = String(Math.min(remainingRequest(request), request.kind === 'cash' ? CASH_LIMIT : 1_000_000_000));
      quantity.placeholder = request.kind === 'cash' ? 'Сумма cash' : 'Количество товара';
      const quantityLabel = request.kind === 'cash' ? 'Сколько перевести' : 'Сколько передать';
      addField(transferForm, quantityLabel, quantity);
      const transfer = button(request.kind === 'cash' ? 'Перевести деньги' : 'Передать товар', 'bg-emerald-600 text-white');
      transfer.type = 'submit';
      transferForm.append(transfer);
      transferForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const amount = Number(quantity.value);
        const max = Number(quantity.max);
        if (!Number.isFinite(amount) || amount <= 0 || amount > max) {
          toast(`Укажите сумму или количество от 0 до ${number(max, request.kind === 'cash' ? 0 : 3)}.`, 'error');
          return;
        }
        setBusy(transfer, true, 'Отправляем…', request.kind === 'cash' ? 'Перевести деньги' : 'Передать товар');
        const payload = {
          recipient_company_id: Number(request.company_id),
          request_id: Number(request.id),
          ...(request.kind === 'cash'
            ? { amount_cash: amount }
            : { item_id: request.item_id, quantity: amount }),
        };
        try {
          const result = await NatAPI.transferAid(payload);
          const confirmation = request.kind === 'cash'
            ? `Переведено ${number(result.cash_amount ?? amount, 0)} cash компании «${companyLabel}».`
            : `Передано ${number(result.item_quantity ?? amount, 3)} ${getItemInfo(request.item_id).unit} · ${itemLabel(request.item_id)} компании «${companyLabel}».`;
          toast(confirmation);
          await refreshAll();
        } catch (error) {
          toast(error?.message || 'Не удалось отправить помощь', 'error');
          setBusy(transfer, false, 'Отправляем…', request.kind === 'cash' ? 'Перевести деньги' : 'Передать товар');
        }
      });
      card.append(transferForm);
      requestsBody.append(card);
    }
  }

  async function refreshData() {
    if (!active) return;
    requestsBody.replaceChildren(el('div', 'text-sm text-slate-500', 'Обновляем заявки…'));
    try {
      const [mineData, requestsData, summaryData] = await Promise.all([
        NatAPI.getMyAidRequest(),
        NatAPI.getAidRequests(),
        NatAPI.getAidSummary(),
      ]);
      if (!active) return;
      const myRequest = mineData?.request || null;
      const requests = Array.isArray(requestsData) ? requestsData : (requestsData?.requests || []);
      renderMine(myRequest);
      renderRequests(requests);
      renderSummary(summaryData?.summary || summaryData || {});
    } catch (error) {
      if (!active) return;
      myRequestBody.replaceChildren(el('div', `${classes.card} text-sm text-rose-600`, error?.message || 'Не удалось загрузить заявки.'));
      requestsBody.replaceChildren(el('div', `${classes.card} text-sm text-rose-600`, 'Попробуйте обновить экран позже.'));
      summaryBody.replaceChildren(el('div', 'text-sm text-rose-600', 'Не удалось загрузить репутацию помощи.'));
      toast(error?.message || 'Не удалось загрузить заявки', 'error');
    }
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (createButton.disabled) return;
    const payload = kindSelect.value === 'cash'
      ? { kind: 'cash', amount_cash: Number(cashInput.value), message: messageInput.value.trim() || null }
      : { kind: 'item', item_id: itemSelect.value, item_quantity: Number(qtyInput.value), message: messageInput.value.trim() || null };
    const amount = payload.kind === 'cash' ? payload.amount_cash : payload.item_quantity;
    if (!Number.isFinite(amount) || amount <= 0 || (payload.kind === 'cash' && amount > CASH_LIMIT)) {
      toast('Проверьте сумму или количество. Для денежной заявки максимум — 100 000 cash.', 'error');
      return;
    }
    if (payload.kind === 'cash' && !payload.message) {
      toast('Укажите в сообщении, на какие расходы нужны деньги.', 'error');
      messageInput.focus();
      return;
    }
    setBusy(createButton, true, 'Публикуем…', 'Опубликовать заявку');
    try {
      await NatAPI.createAidRequest(payload);
      toast('Заявка опубликована. Другие компании увидят её в списке помощи.');
      await refreshAll();
    } catch (error) {
      toast(error?.message || 'Не удалось создать заявку', 'error');
      setBusy(createButton, false, 'Публикуем…', 'Опубликовать заявку');
    }
  });

  await refreshData();
  return () => { active = false; };
}

export default renderCompanyAidPanel;
