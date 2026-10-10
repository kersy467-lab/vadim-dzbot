import { NatAPI } from '../api.js?v=20261010_competition_v1';

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function number(value, digits = 2) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function disclosure(title, content) {
  return `<details class="next-game-disclosure"><summary>${title}</summary>${content}</details>`;
}

export function renderBank(state) {
  const banking = state.banking || {};
  const accounts = banking.accounts || [];
  const providers = banking.providers || [];
  const accountBankIds = new Set(accounts.map((account) => Number(account.bank_company_id)));
  const accountCards = providers.map((provider) => {
    const ownBank = Number(provider.bank_company_id) === Number(state.company?.id);
    const opened = accountBankIds.has(Number(provider.bank_company_id));
    const action = ownBank
      ? '<span class="next-game-bank-account-state">Собственный банк</span>'
      : opened
        ? '<span class="next-game-bank-account-state is-open">Счёт открыт</span>'
        : `<button type="button" data-bank-account-open="${esc(provider.bank_company_id)}" class="next-game-secondary">Открыть счёт</button>`;
    return `<article class="next-game-bank-account"><div><b>${esc(provider.bank_name)}</b><span>Комиссия за платёж ${number(provider.fee_percent, 2)}%</span><small>Услуги: ${provider.branches.map(esc).join(' · ')}</small></div>${action}</article>`;
  }).join('');
  const payeeOptions = (banking.companies || []).map((company) =>
    `<option value="${esc(company.id)}">${esc(company.name)} · #${esc(company.id)}</option>`
  ).join('');
  const paymentAccounts = accounts.map((account) =>
    `<option value="${esc(account.bank_company_id)}">${esc(account.bank_name)} · комиссия ${number(Number(account.fee_bps) / 100, 2)}%</option>`
  ).join('');
  const corporatePaymentForm = paymentAccounts && payeeOptions
    ? `<article class="next-game-bank-loan next-game-bank-payment-form"><h3>Межкорпоративный перевод</h3><p>Получатель получает всю сумму; комиссию оплачивает отправитель. Банк зарабатывает на реальных платежах.</p><label for="next-game-payment-bank">Через банк</label><select id="next-game-payment-bank">${paymentAccounts}</select><label for="next-game-payment-payee">Компания-получатель</label><select id="next-game-payment-payee">${payeeOptions}</select><label for="next-game-payment-amount">Сумма, от 100 cash</label><input id="next-game-payment-amount" type="number" min="100" max="10000000" step="0.01" value="1000" /><button type="button" data-bank-payment-send class="next-game-primary">Отправить платёж</button></article>`
    : '<p class="next-game-bank-note">Чтобы отправлять переводы, открой расчётный счёт в банке. Получатель также должен иметь активный счёт в том же банке.</p>';
  const paymentHistory = (banking.payments || []).slice(0, 8).map((payment) => {
    const date = payment.created_at
      ? new Date(payment.created_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
      : '';
    return `<li><span>${esc(payment.payer_name)} → ${esc(payment.payee_name)} через ${esc(payment.bank_name)}<small>${esc(date)} · комиссия ${number(payment.fee)} cash</small></span><b>${number(payment.amount)} cash</b></li>`;
  }).join('');
  const bankSummary = banking.bank_summary || {};
  const loanOffers = (banking.loan_offers || []).filter((offer) =>
    accountBankIds.has(Number(offer.bank_company_id))
  );
  const loanOfferCards = loanOffers.map((offer) => {
    const max = Number(offer.max_amount || 0);
    const enabled = max >= 1_000;
    return disclosure(`Выбрать кредит · ${esc(offer.bank_name)}`, `<article class="next-game-bank-account next-game-bank-loan-offer" data-bank-loan-offer="${esc(offer.bank_company_id)}"><div><b>${esc(offer.bank_name)} · корпоративный кредит</b><span>До ${number(max, 0)} cash · ${number(Number(offer.daily_rate) * 100, 2)}% за сутки</span><small>Выдача из средств банка; без активного долга у компании.</small></div><div class="next-game-bank-loan-controls"><label>Сумма<input data-bank-corporate-loan-amount type="number" min="1000" max="${max}" step="100" value="${Math.min(5_000, max)}" /></label><label>Срок<select data-bank-corporate-loan-term><option value="1">1 день</option><option value="7" selected>7 дней</option><option value="30">30 дней</option></select></label><button type="button" data-bank-corporate-loan-request class="next-game-secondary" ${enabled ? '' : 'disabled'}>Взять кредит</button></div></article>`);
  }).join('');
  const loanRows = (banking.loans || []).map((loan) => {
    const isBorrower = Number(loan.borrower_company_id) === Number(state.company?.id);
    const activeBorrowerLoan = isBorrower && loan.status === 'ACTIVE';
    const title = isBorrower
      ? `Кредит от ${esc(loan.bank_name)}`
      : `Кредит компании ${esc(loan.borrower_name)}`;
    const action = activeBorrowerLoan
      ? `<button type="button" data-bank-business-loan-repay="${esc(loan.id)}" class="next-game-secondary">Погасить ${number(loan.due_amount)} cash</button>`
      : `<span class="next-game-bank-account-state ${loan.status === 'PAID' ? 'is-open' : ''}">${loan.status === 'WRITTEN_OFF' ? 'Списан при банкротстве' : loan.status === 'PAID' ? 'Погашен' : 'Выдан'}</span>`;
    return `<article class="next-game-bank-account"><div><b>${title}</b><span>${number(loan.principal)} cash · ${number(Number(loan.daily_rate) * 100, 2)}% в сутки · ${number(loan.term_days, 0)} дн.</span><small>К возврату: ${number(loan.due_amount)} cash · срок ${new Date(loan.due_at).toLocaleDateString('ru-RU')}</small></div>${action}</article>`;
  }).join('');
  const directFinance = banking.direct_finance || {};
  const directOffers = (directFinance.contracts || []).map((contract) => {
    const isLender = Number(contract.lender_company_id) === Number(state.company?.id);
    const isBorrower = Number(contract.borrower_company_id) === Number(state.company?.id);
    const statusLabels = { OPEN: 'Ожидает ответа', ACTIVE: 'Активен', OVERDUE: 'Просрочен', PAID: 'Погашен', WRITTEN_OFF: 'Списан при банкротстве', CANCELLED: 'Отменён' };
    let action = `<span class="next-game-bank-account-state ${contract.status === 'PAID' ? 'is-open' : ''}">${statusLabels[contract.status] || esc(contract.status)}</span>`;
    if (contract.status === 'OPEN' && isBorrower) action = `<button type="button" data-next-finance-accept="${esc(contract.id)}" class="next-game-primary">Принять займ</button>`;
    else if (contract.status === 'OPEN' && isLender) action = `<button type="button" data-next-finance-cancel="${esc(contract.id)}" class="next-game-secondary">Отозвать</button>`;
    else if (['ACTIVE', 'OVERDUE'].includes(contract.status) && isBorrower) action = `<button type="button" data-next-finance-repay="${esc(contract.id)}" class="next-game-primary">Погасить ${number(contract.due_amount)} cash</button>`;
    const counterparty = isLender ? contract.borrower_name : contract.lender_name;
    const side = isLender ? 'Займ компании' : 'Займ от компании';
    return `<article class="next-game-bank-account"><div><b>${side} ${esc(counterparty)}</b><span>${number(contract.principal)} cash · ${number(contract.daily_rate_percent)}% в сутки · ${number(contract.term_days, 0)} дн.</span><small>${contract.status === 'OPEN' && isLender ? 'Сумма зарезервирована до принятия или отзыва.' : `К возврату: ${number(contract.due_amount)} cash${contract.due_at ? ` · срок ${new Date(contract.due_at).toLocaleDateString('ru-RU')}` : ''}`}</small></div>${action}</article>`;
  }).join('');
  const companyCash = Number(state.company?.cash || 0);
  const directOfferForm = payeeOptions
    ? `<article class="next-game-bank-loan next-game-direct-finance-form"><h3>Предложить займ компании</h3><p>Сумма резервируется при публикации. Заёмщик принимает предложение, затем возвращает сумму и простые проценты по фактическим дням.</p><label for="next-game-finance-borrower">Компания-заёмщик</label><select id="next-game-finance-borrower">${payeeOptions}</select><label for="next-game-finance-principal">Сумма от 1 000 cash</label><input id="next-game-finance-principal" type="number" min="1000" max="${Math.min(100000, companyCash)}" step="100" value="${Math.min(5000, 100000, Math.max(1000, companyCash))}" /><label for="next-game-finance-rate">Ставка за сутки, базисные пункты (100 = 1%)</label><input id="next-game-finance-rate" type="number" min="0" max="100" step="5" value="25" /><label for="next-game-finance-term">Срок</label><select id="next-game-finance-term"><option value="1">1 день</option><option value="7" selected>7 дней</option><option value="30">30 дней</option></select><button type="button" data-next-finance-offer class="next-game-primary" ${companyCash < 1000 ? 'disabled' : ''}>Зарезервировать и предложить</button></article>`
    : '<p class="next-game-bank-note">Для прямого займа нужна ещё одна компания в новой игре.</p>';
  const reserves = (state.market || []).map((item) => `<li><span>${esc(item.name)}</span><b>${number(item.npc_quantity, 3)} ${esc(item.unit)}</b></li>`).join('');
  const activity = (state.recent_activity || []).filter((row) => Number(row.cash_change)).slice(0, 6).map((row) => {
    const when = row.created_at ? new Date(row.created_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '';
    return `<li><span>${esc(row.action)}</span><b>${Number(row.cash_change) > 0 ? '+' : ''}${number(row.cash_change)} cash</b><time>${esc(when)}</time></li>`;
  }).join('');
  const deposits = (state.deposits || []).map((deposit) => {
    const due = deposit.matures_at
      ? new Date(deposit.matures_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
      : '';
    const active = deposit.status === 'ACTIVE';
    const action = active && deposit.is_matured
      ? `<button type="button" class="next-game-primary" data-bank-deposit-withdraw="${esc(deposit.id)}">Забрать вклад</button>`
      : active ? `<span class="next-game-deposit-wait">Доступен ${esc(due)}</span>` : '<span class="next-game-deposit-wait">Выплачен</span>';
    return `<article class="next-game-bank-loan next-game-deposit"><div><h3>Срочный вклад · ${number(deposit.term_days, 0)} дн.</h3><p>Вложено ${number(deposit.principal)} cash · доход ${number(deposit.interest)} cash · ставка ${number(Number(deposit.daily_rate) * 100, 2)}% в день.</p><b>Выплата: ${number(deposit.maturity_amount)} cash</b></div>${action}</article>`;
  }).join('');
  const loan = state.bank_loan;
  const loanDue = loan?.due_at ? new Date(loan.due_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '';
  const loanCard = loan
    ? `<article class="next-game-bank-loan is-active"><div><h3>Активный кредит</h3><p>Основной долг ${number(loan.principal)} cash · начислено ${number(loan.interest_due)} cash за ${number(loan.accrual_days, 0)} дн. Срок до ${esc(loanDue)}.</p><b>К погашению: ${number(loan.repayment_amount)} cash</b></div><button type="button" data-bank-repay class="next-game-primary">Погасить</button></article>`
    : `<article class="next-game-bank-loan"><div><h3>Кредит компании</h3><p>До ${number(state.bank_credit_limit, 0)} cash из резерва банка. Проценты — 1% за начатые сутки, минимум за одни сутки; деньги выдаются из казны.</p></div><label for="next-game-loan-amount">Сумма, от 1 000 до ${number(state.bank_credit_limit, 0)} cash</label><input id="next-game-loan-amount" type="number" min="1000" max="${Number(state.bank_credit_limit || 0)}" step="1000" value="${Math.min(10_000, Number(state.bank_credit_limit || 0))}" /><button type="button" data-bank-loan-request class="next-game-primary" ${Number(state.bank_credit_limit) < 1_000 ? 'disabled' : ''}>Взять кредит</button></article>`;
  const depositValue = Math.min(10_000, companyCash);
  const depositForm = `<article class="next-game-bank-loan next-game-deposit-form"><div><h3>Срочный вклад</h3><p>Доход 0,25% за сутки, ставка фиксируется при открытии. Срок — 1–30 дней; проценты и сумма выплаты заранее резервируются в казне.</p></div><label for="next-game-deposit-amount">Сумма, минимум 1 000 cash</label><input id="next-game-deposit-amount" type="number" min="1000" max="${companyCash}" step="100" value="${depositValue}" /><label for="next-game-deposit-term">Срок</label><select id="next-game-deposit-term"><option value="1">1 день</option><option value="7" selected>7 дней</option><option value="30">30 дней</option></select><button type="button" data-bank-deposit-open class="next-game-primary" ${companyCash < 1_000 ? 'disabled' : ''}>Открыть вклад</button></article>`;
  return `<section class="next-game-panel next-game-bank"><div><h2>Расчётный банк 2.0</h2><p>Отдельная казна новой игры: выдаёт стартовый капитал, принимает оплату за ресурсы и платит за проданные товары.</p></div><article class="next-game-bank-balance"><span>Свободный резерв казны · всего ${number(state.treasury?.total_cash)} cash, из них ${number(state.treasury?.reserved_for_deposits)} зарезервировано под вклады</span><b>${number(state.treasury?.cash)} cash</b></article>${loan ? loanCard : disclosure('Открыть кредит компании', loanCard)}${disclosure('Разместить срочный вклад', depositForm)}${deposits ? `<div class="next-game-deposit-list"><h3>Мои вклады</h3>${deposits}</div>` : ''}<section class="next-game-bank-clients"><header><div><h3>Расчётные счета и платежи</h3><p>Банковские компании открывают счета другим корпорациям и получают комиссию с перевода.</p></div><span>${number(bankSummary.customer_accounts, 0)} клиентов · ${number(bankSummary.fee_income)} cash комиссий · ${number(bankSummary.loan_interest_income)} cash процентов</span></header>${accountCards ? `<div class="next-game-bank-account-list">${accountCards}</div>` : '<p class="next-game-bank-note">Пока нет банка с открытым обслуживанием счетов.</p>'}${disclosure('Открыть форму перевода', corporatePaymentForm)}<div class="next-game-bank-loans"><h3>Корпоративное кредитование</h3><p>Получить кредит можно в банке с корпоративной веткой и открытым счётом. Ставка начисляется только на фактически выданную сумму и возвращается банку.</p>${loanOfferCards || '<p class="next-game-bank-note">Пока нет доступного предложения. Открой счёт и выбери банк с корпоративным кредитованием.</p>'}${loanRows || '<p class="next-game-bank-note">Активных или закрытых корпоративных кредитов пока нет.</p>'}</div><div class="next-game-bank-loans"><h3>Прямые займы компаний</h3><p>Компании могут финансировать друг друга без банка. Незакрытое предложение резервирует cash; принятие фиксирует срок и ставку, а погашение возвращает сумму кредитору.</p>${disclosure('Предложить займ компании', directOfferForm)}${directOffers || '<p class="next-game-bank-note">Займов и предложений пока нет.</p>'}</div>${disclosure('Последние переводы', `<div class="next-game-bank-reserve"><ul>${paymentHistory || '<li>Платежей пока нет</li>'}</ul></div>`)}</section>${disclosure('Резерв по текущему маршруту', `<div class="next-game-bank-reserve"><ul>${reserves || '<li>Сначала открой ветку развития</li>'}</ul></div>`)}${disclosure('История денежных операций', `<div class="next-game-bank-reserve"><ul>${activity || '<li>Платёжных операций пока нет</li>'}</ul></div>`)}<p class="next-game-bank-note">Казённые операции записываются в двойной журнал. Сделки между компаниями имеют отдельную историю на рынке. Старые балансы и рынок не участвуют.</p></section>`;
}

export function bindBankActions(container, showToast, state, refresh) {
  container.querySelectorAll('[data-bank-account-open]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await NatAPI.openNextGameCorporateAccount(button.dataset.bankAccountOpen);
        showToast(`Расчётный счёт открыт в банке «${result.account.bank_name}»`, 'success');
        await refresh();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
  });
  container.querySelector('[data-bank-payment-send]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const bankId = Number(container.querySelector('#next-game-payment-bank')?.value);
    const payeeId = Number(container.querySelector('#next-game-payment-payee')?.value);
    const amount = Number(container.querySelector('#next-game-payment-amount')?.value);
    if (!Number.isInteger(bankId) || !Number.isInteger(payeeId)
        || !Number.isFinite(amount) || amount < 100 || amount > 10_000_000) {
      return showToast('Проверь банк, получателя и сумму перевода', 'error');
    }
    button.disabled = true;
    try {
      const result = await NatAPI.makeNextGameCompanyPayment(bankId, payeeId, amount);
      showToast(`Перевод выполнен. Комиссия банка: ${number(result.payment.fee)} cash`, 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
  container.querySelectorAll('[data-bank-corporate-loan-request]').forEach((button) => {
    button.addEventListener('click', async () => {
      const card = button.closest('[data-bank-loan-offer]');
      const amount = Number(card?.querySelector('[data-bank-corporate-loan-amount]')?.value);
      const termDays = Number(card?.querySelector('[data-bank-corporate-loan-term]')?.value);
      const bankId = Number(card?.dataset.bankLoanOffer);
      if (!Number.isInteger(bankId) || !Number.isFinite(amount) || amount < 1_000
          || amount > 100_000 || !Number.isInteger(termDays) || termDays < 1 || termDays > 30) {
        return showToast('Проверь сумму кредита от 1 000 cash и срок от 1 до 30 дней', 'error');
      }
      button.disabled = true;
      try {
        const result = await NatAPI.requestNextGameBusinessLoan(bankId, amount, termDays);
        showToast(`Банк выдал ${number(result.loan.principal)} cash`, 'success');
        await refresh();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
  });
  container.querySelectorAll('[data-bank-business-loan-repay]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await NatAPI.repayNextGameBusinessLoan(button.dataset.bankBusinessLoanRepay);
        showToast(`Кредит погашен: ${number(result.paid_amount)} cash`, 'success');
        await refresh();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
  });
  container.querySelector('[data-next-finance-offer]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const borrowerId = Number(container.querySelector('#next-game-finance-borrower')?.value);
    const principal = Number(container.querySelector('#next-game-finance-principal')?.value);
    const rateBps = Number(container.querySelector('#next-game-finance-rate')?.value);
    const termDays = Number(container.querySelector('#next-game-finance-term')?.value);
    if (!Number.isInteger(borrowerId) || !Number.isFinite(principal) || principal < 1_000
        || principal > Math.min(100_000, Number(state.company?.cash || 0))
        || !Number.isInteger(rateBps) || rateBps < 0 || rateBps > 100
        || !Number.isInteger(termDays) || termDays < 1 || termDays > 30) {
      return showToast('Проверь компанию, сумму, ставку и срок займа', 'error');
    }
    button.disabled = true;
    try {
      const result = await NatAPI.createNextGameDirectLoanOffer(borrowerId, principal, rateBps, termDays);
      showToast(`Предложение создано: ${number(result.contract.principal)} cash зарезервировано`, 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
  container.querySelectorAll('[data-next-finance-accept]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await NatAPI.acceptNextGameDirectLoanOffer(button.dataset.nextFinanceAccept);
        showToast(`Займ принят: ${number(result.contract.principal)} cash`, 'success');
        await refresh();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
  });
  container.querySelectorAll('[data-next-finance-cancel]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await NatAPI.cancelNextGameDirectLoanOffer(button.dataset.nextFinanceCancel);
        showToast(`Предложение отменено, возвращено ${number(result.contract.principal)} cash`, 'success');
        await refresh();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
  });
  container.querySelectorAll('[data-next-finance-repay]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await NatAPI.repayNextGameDirectLoan(button.dataset.nextFinanceRepay);
        showToast(`Займ погашен: ${number(result.paid_amount)} cash`, 'success');
        await refresh();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
  });
  container.querySelector('[data-bank-loan-request]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const amount = Number(container.querySelector('#next-game-loan-amount')?.value);
    if (!Number.isFinite(amount) || amount < 1_000 || amount > Number(state.bank_credit_limit)) return showToast('Укажи кредит от 1 000 cash в пределах доступного лимита банка', 'error');
    button.disabled = true;
    try {
      const result = await NatAPI.requestNextGameBankLoan(amount);
      showToast(`Банк выдал ${number(result.loan.principal)} cash`, 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
  container.querySelector('[data-bank-repay]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const result = await NatAPI.repayNextGameBankLoan();
      showToast(`Кредит погашен: ${number(result.paid_amount)} cash`, 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
  container.querySelector('[data-bank-deposit-open]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const amount = Number(container.querySelector('#next-game-deposit-amount')?.value);
    const termDays = Number(container.querySelector('#next-game-deposit-term')?.value);
    if (!Number.isFinite(amount) || amount < 1_000 || amount > Number(state.company?.cash || 0)) return showToast('Укажи вклад от 1 000 cash в пределах баланса компании', 'error');
    button.disabled = true;
    try {
      const result = await NatAPI.openNextGameBankDeposit(amount, termDays);
      showToast(`Вклад открыт. Доход к сроку: ${number(result.deposit.interest)} cash`, 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
  container.querySelectorAll('[data-bank-deposit-withdraw]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await NatAPI.withdrawNextGameBankDeposit(button.dataset.bankDepositWithdraw);
        showToast(`Вклад выплачен: ${number(result.paid_amount)} cash, доход ${number(result.interest)} cash`, 'success');
        await refresh();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
  });
}
