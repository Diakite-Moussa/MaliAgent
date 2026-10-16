import { Injectable, signal, computed, inject, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../auth.service';
import { environment } from '../../environments/environment';
import {
  BusinessInfo,
  Kpis,
  Order,
  Product,
  PaymentItem,
  PlatformStats,
  PlatformBusiness,
  PlatformUser,
  PlatformHealth,
  PlatformAuditLog,
  DriverMission,
  DriverSummary,
  MerchantMission,
  MerchantDriver,
  MerchantPartner,
  AgentConfiguration,
  KnowledgeDocument,
  ProductCategory,
} from '../models/dashboard.models';

@Injectable({
  providedIn: 'root',
})
export class DashboardStateService implements OnDestroy {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  readonly apiUrl = environment.apiUrl;

  private autoRefreshTimer: any = null;

  // Mode de visualisation : 'platform' (Super Admin), 'merchant' (Boutique), 'driver' (Livreur Mobile)
  readonly viewMode = signal<'platform' | 'merchant' | 'driver'>('merchant');

  // États globaux UI
  readonly loading = signal<boolean>(false);
  readonly backendConnected = signal<boolean>(true);
  readonly toastMessage = signal<string | null>(null);

  // ================= DONNÉES COMMERÇANT =================
  readonly business = signal<BusinessInfo>({
    id: '',
    name: 'MaliAgent Boutique',
    currency: 'XOF',
    whatsapp_phone_number: '15556640413',
  });

  readonly kpis = signal<Kpis>({
    total_revenue: 0,
    today_revenue: 0,
    today_orders_count: 0,
    pending_orders_count: 0,
    total_customers: 0,
    low_stock_count: 0,
    pending_handoffs_count: 0,
  });

  readonly orders = signal<Order[]>([]);
  readonly products = signal<Product[]>([]);
  readonly categories = signal<ProductCategory[]>([]);
  readonly lowStockProducts = signal<any[]>([]);
  readonly handoffs = signal<any[]>([]);
  readonly payments = signal<PaymentItem[]>([]);
  readonly merchantMissions = signal<MerchantMission[]>([]);
  readonly merchantDrivers = signal<MerchantDriver[]>([]);
  readonly merchantPartners = signal<MerchantPartner[]>([]);
  readonly agentConfig = signal<AgentConfiguration | null>(null);
  readonly isSavingAgentConfig = signal<boolean>(false);
  readonly knowledgeDocuments = signal<KnowledgeDocument[]>([]);

  // ================= DONNÉES SUPER ADMIN =================
  readonly platformStats = signal<PlatformStats>({
    businesses: { total: 0, active: 0, suspended: 0 },
    orders: { total_count: 0, total_gmv_fcfa: 0 },
    engagement: { total_customers: 0, total_conversations: 0, total_handoffs: 0 },
    users_count: 0,
  });
  readonly platformBusinesses = signal<PlatformBusiness[]>([]);
  readonly platformUsers = signal<PlatformUser[]>([]);
  readonly platformHealth = signal<PlatformHealth | null>(null);
  readonly platformAuditLogs = signal<PlatformAuditLog[]>([]);

  // ================= DONNÉES LIVREUR (SPRINT 11) =================
  readonly driverMissions = signal<DriverMission[]>([]);
  readonly driverSummary = signal<DriverSummary | null>(null);

  readonly activeDriverMissions = computed(() =>
    this.driverMissions().filter((m) => m.status !== 'delivered' && m.status !== 'cancelled')
  );

  readonly completedDriverMissions = computed(() =>
    this.driverMissions().filter((m) => m.status === 'delivered')
  );

  showToast(message: string, durationMs: number = 4000) {
    this.toastMessage.set(message);
    setTimeout(() => {
      if (this.toastMessage() === message) {
        this.toastMessage.set(null);
      }
    }, durationMs);
  }

  // ================= CYCLE D'AUTO-REFRESH =================
  startAutoRefresh() {
    this.stopAutoRefresh();
    this.autoRefreshTimer = setInterval(() => {
      if (this.authService.isAuthenticated()) {
        if (this.viewMode() === 'platform') {
          this.loadPlatformStats();
        } else if (this.viewMode() === 'driver') {
          this.loadDriverMissions();
        } else {
          this.loadStats();
          this.loadHandoffs();
          this.loadMerchantDeliveries();
        }
      }
    }, 15000);
  }

  stopAutoRefresh() {
    if (this.autoRefreshTimer) {
      clearInterval(this.autoRefreshTimer);
      this.autoRefreshTimer = null;
    }
  }

  ngOnDestroy() {
    this.stopAutoRefresh();
  }

  // ================= CHARGEMENT COMMERÇANT =================
  refreshMerchantAll() {
    this.loading.set(true);
    this.loadStats();
    this.loadOrders();
    this.loadProducts();
    this.loadCategories();
    this.loadHandoffs();
    this.loadMerchantDeliveries();
    this.loadPayments();
    this.loadAgentConfig();
    this.loadKnowledgeDocuments();
  }

  loadStats() {
    this.http.get<any>(`${this.apiUrl}/api/dashboard/stats`).subscribe({
      next: (data) => {
        if (data.business) this.business.set(data.business);
        if (data.kpis) this.kpis.set(data.kpis);
        this.lowStockProducts.set(data.low_stock_products || []);
        this.backendConnected.set(true);
      },
      error: () => {
        this.backendConnected.set(false);
      },
    });
  }

  loadOrders() {
    this.http.get<{ orders: Order[]; total: number }>(`${this.apiUrl}/api/orders`).subscribe({
      next: (data) => {
        this.orders.set(data.orders || []);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
      },
    });
  }

  loadProducts() {
    this.http.get<Product[]>(`${this.apiUrl}/api/products`).subscribe({
      next: (data) => {
        this.products.set(data || []);
      },
    });
  }

  loadCategories() {
    this.http.get<ProductCategory[]>(`${this.apiUrl}/api/categories`).subscribe({
      next: (data) => {
        this.categories.set(data || []);
      },
      error: (err) => console.error('Erreur chargement catégories:', err),
    });
  }

  loadHandoffs() {
    this.http.get<{ handoffs: any[]; total: number }>(`${this.apiUrl}/api/dashboard/handoffs`).subscribe({
      next: (data) => {
        this.handoffs.set(data.handoffs || []);
      },
    });
  }

  loadMerchantDeliveries() {
    this.http.get<{ missions: MerchantMission[]; total: number }>(`${this.apiUrl}/api/delivery/missions`).subscribe({
      next: (data) => {
        this.merchantMissions.set(data?.missions || []);
      },
      error: (err) => console.error('Erreur chargement missions:', err),
    });
    this.http.get<MerchantDriver[]>(`${this.apiUrl}/api/delivery/drivers`).subscribe({
      next: (data) => {
        this.merchantDrivers.set(Array.isArray(data) ? data : []);
      },
      error: (err) => console.error('Erreur chargement livreurs:', err),
    });
    this.http.get<MerchantPartner[]>(`${this.apiUrl}/api/delivery/partners`).subscribe({
      next: (data) => {
        this.merchantPartners.set(Array.isArray(data) ? data : []);
      },
      error: (err) => console.error('Erreur chargement partenaires:', err),
    });
  }

  loadPayments() {
    this.http.get<any>(`${this.apiUrl}/api/payments`).subscribe({
      next: (data) => {
        const list = Array.isArray(data) ? data : (data?.payments || []);
        this.payments.set(list);
      },
      error: (err) => {
        console.error('Erreur chargement paiements:', err);
      },
    });
  }

  loadAgentConfig() {
    this.http.get<AgentConfiguration>(`${this.apiUrl}/api/dashboard/agent/config`).subscribe({
      next: (cfg) => {
        this.agentConfig.set(cfg);
      },
      error: (err) => {
        console.error('Erreur chargement configuration agent IA:', err);
      },
    });
  }

  loadKnowledgeDocuments() {
    this.http.get<KnowledgeDocument[]>(`${this.apiUrl}/api/knowledge`).subscribe({
      next: (docs) => {
        this.knowledgeDocuments.set(Array.isArray(docs) ? docs : []);
      },
      error: (err) => {
        console.error('Erreur chargement base de connaissances:', err);
      },
    });
  }

  uploadKnowledgeDocument(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<KnowledgeDocument>(`${this.apiUrl}/api/knowledge/upload`, formData);
  }

  deleteKnowledgeDocument(documentId: string) {
    return this.http.delete<{ status: string; document_id: string }>(`${this.apiUrl}/api/knowledge/${documentId}`);
  }

  updateAgentConfig(payload: Partial<AgentConfiguration>, onSuccess?: () => void) {
    this.isSavingAgentConfig.set(true);
    this.http.put<AgentConfiguration>(`${this.apiUrl}/api/dashboard/agent/config`, payload).subscribe({
      next: (updated) => {
        this.agentConfig.set(updated);
        this.isSavingAgentConfig.set(false);
        this.showToast("✓ Configuration de l'agent IA enregistrée avec succès !");
        if (onSuccess) onSuccess();
      },
      error: (err) => {
        this.isSavingAgentConfig.set(false);
        this.showToast(err.error?.detail || "Erreur lors de l'enregistrement de l'agent IA");
      },
    });
  }

  // ================= CHARGEMENT SUPER ADMIN =================
  loadPlatformAll() {
    this.loading.set(true);
    this.loadPlatformStats();
    this.loadPlatformBusinesses();
    this.loadPlatformUsers();
    this.loadPlatformHealth();
    this.loadPlatformAuditLogs();
  }

  loadPlatformStats() {
    this.http.get<PlatformStats>(`${this.apiUrl}/api/platform/stats`).subscribe({
      next: (data) => {
        this.platformStats.set(data);
        this.backendConnected.set(true);
        this.loading.set(false);
      },
      error: () => {
        this.backendConnected.set(false);
        this.loading.set(false);
      },
    });
  }

  loadPlatformBusinesses() {
    this.http.get<PlatformBusiness[]>(`${this.apiUrl}/api/platform/businesses`).subscribe({
      next: (data) => {
        this.platformBusinesses.set(data || []);
      },
    });
  }

  loadPlatformUsers() {
    this.http.get<PlatformUser[]>(`${this.apiUrl}/api/platform/users`).subscribe({
      next: (data) => {
        this.platformUsers.set(data || []);
      },
    });
  }

  loadPlatformHealth() {
    this.http.get<PlatformHealth>(`${this.apiUrl}/api/platform/health`).subscribe({
      next: (data) => {
        this.platformHealth.set(data);
      },
    });
  }

  loadPlatformAuditLogs(actionFilter?: string) {
    let url = `${this.apiUrl}/api/platform/audit-logs?page=1&page_size=50`;
    if (actionFilter) {
      url += `&action=${encodeURIComponent(actionFilter)}`;
    }
    this.http.get<PlatformAuditLog[]>(url).subscribe({
      next: (data) => {
        this.platformAuditLogs.set(data || []);
      },
    });
  }

  // ================= CHARGEMENT LIVREUR =================
  loadDriverMissions() {
    this.http.get<{ missions: DriverMission[]; total: number }>(`${this.apiUrl}/api/delivery/driver/missions`).subscribe({
      next: (data) => {
        this.driverMissions.set(data.missions || []);
      },
    });
    this.loadDriverSummary();
  }

  loadDriverSummary() {
    this.http.get<DriverSummary>(`${this.apiUrl}/api/delivery/driver/summary`).subscribe({
      next: (data) => {
        this.driverSummary.set(data);
      },
      error: () => {},
    });
  }
}
