/**
 * Reactive State Management for Natbirzha
 */

class NatStateStore {
  constructor() {
    this.user = null;
    this.company = null;
    this.inventory = {};
    this.inventoryTotal = {};
    this.inventoryReserved = {};
    this.factories = [];
    this.nav = 0;
    this.currentTab = 'overview';
    this.maintenanceMode = false;
    this.listeners = new Set();
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      try {
        listener(this);
      } catch (err) {
        console.error('State listener error:', err);
      }
    }
  }

  setUser(user) {
    this.user = user;
    this.notify();
  }

  setMaintenanceMode(mode) {
    this.maintenanceMode = Boolean(mode);
    this.notify();
  }

  setCompany(companyData) {
    if (!companyData) {
      this.company = null;
      this.inventory = {};
      this.inventoryTotal = {};
      this.inventoryReserved = {};
      this.factories = [];
      this.nav = 0;
    } else {
      this.company = companyData;
      // Normalize company_id to id for consistency
      if (companyData.company_id && !companyData.id) {
        this.company.id = companyData.company_id;
      }
      this.inventory = companyData.inventory_available || companyData.inventory || {};
      this.inventoryTotal = companyData.inventory_total || companyData.inventory || {};
      this.inventoryReserved = companyData.inventory_reserved || {};
      if (Array.isArray(companyData.factories) && companyData.factories.length > 0) {
        this.factories = companyData.factories;
      }
      this.nav = companyData.nav || companyData.audited_nav || companyData.cash || 0;
    }
    this.notify();
  }

  updateCompany(partial) {
    if (this.company && partial && typeof partial === 'object') {
      for (const [k, v] of Object.entries(partial)) {
        if (v !== undefined) {
          this.company[k] = v;
        }
      }
      if (partial.inventory_available !== undefined) this.inventory = partial.inventory_available;
      else if (partial.inventory !== undefined) this.inventory = partial.inventory;
      if (partial.inventory_total !== undefined) this.inventoryTotal = partial.inventory_total;
      else if (partial.inventory !== undefined) this.inventoryTotal = partial.inventory;
      if (partial.inventory_reserved !== undefined) this.inventoryReserved = partial.inventory_reserved;
      if (Array.isArray(partial.factories) && partial.factories.length > 0) {
        this.factories = partial.factories;
      }
      if (partial.nav !== undefined) this.nav = partial.nav;
      else if (partial.audited_nav !== undefined) this.nav = partial.audited_nav;
      this.notify();
    }
  }

  setTab(tab) {
    this.currentTab = tab;
    this.notify();
  }

  hasCompany() {
    return !!this.company && (!!this.company.id || !!this.company.company_id);
  }
}

export const store = new NatStateStore();
