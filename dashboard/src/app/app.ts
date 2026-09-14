import { Component, OnInit, OnDestroy, signal, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { AuthService } from './auth.service';

export interface BusinessInfo {
  id: string;
  name: string;
  currency: string;
  whatsapp_phone_number: string;
}

export interface Kpis {
  total_revenue: number;
  today_revenue: number;
  today_orders_count: number;
  pending_orders_count: number;
  total_customers: number;
  low_stock_count: number;
  pending_handoffs_count: number;
}

export interface OrderItem {
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface Order {
  id: string;
  short_id: string;
  status: 'pending' | 'confirmed' | 'delivered' | 'cancelled';
  delivery_address: string;
  delivery_fee: number;
  total_amount: number;
  created_at: string;
  customer: {
    id: string;
    phone: string;
    name: string | null;
  };
  items: OrderItem[];
  invoice: {
    number: string | null;
    status: string | null;
    download_url: string | null;
  };
}

export interface Product {
  id: string;
  business_id: string;
  name: string;
  category: string;
  price: number;
  stock_quantity: number;
  is_low_stock: boolean;
  is_out_of_stock: boolean;
}

// ================= TYPES SUPER ADMIN PLATEFORME =================

export interface PlatformStats {
  businesses: { total: number; active: number; suspended: number };
  orders: { total_count: number; total_gmv_fcfa: number };
  engagement: { total_customers: number; total_conversations: number; total_handoffs: number };
  users_count: number;
}

export interface PlatformBusiness {
  id: string;
  name: string;
  whatsapp_phone_number: string;
  currency: string;
  is_active: boolean;
  created_at: string | null;
  orders_count: number;
  total_revenue: number;
  products_count: number;
  users_count: number;
}

export interface PlatformUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  is_active: boolean;
  business_id: string | null;
  business_name: string | null;
  created_at: string | null;
}

export interface PlatformHealth {
  status: string;
  components: {
    api: { status: string; version: string; environment: string };
    database: { status: string; engine: string };
    llm_provider: { model: string; base_url: string; configured: boolean };
    whatsapp_meta: { configured: boolean; phone_number_id: string };
  };
}

export interface PlatformAuditLog {
  id: string;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  business_id: string | null;
  ip_address: string | null;
  details: any;
  created_at: string | null;
}

// ================= TYPES LIVREUR MOBILE (SPRINT 11) =================

export interface DriverMission {
  id: string;
  order_id: string;
  status: 'pending' | 'assigned' | 'picked_up' | 'in_transit' | 'delivered' | 'failed' | 'cancelled';
  pickup_address: string;
  delivery_address: string;
  customer_name: string | null;
  customer_phone: string;
  otp_verified: boolean;
  current_latitude: number | null;
  current_longitude: number | null;
  navigation: {
    google_maps: string;
    waze: string;
  };
  assigned_at: string | null;
  picked_up_at: string | null;
  delivered_at: string | null;
  notes: string | null;
  created_at: string;
}

// ================= TYPES FLOTTE & LOGISTIQUE COMMERÇANT (SPRINT 12) =================

export interface MerchantMission {
  id: string;
  order_id: string;
  status: 'pending' | 'assigned' | 'picked_up' | 'in_transit' | 'delivered' | 'failed' | 'cancelled';
  assignment_type: 'internal' | 'partner';
  driver_id: string | null;
  driver_name: string | null;
  driver_phone: string | null;
  partner_id: string | null;
  partner_name: string | null;
  pickup_address: string;
  delivery_address: string;
  customer_name: string | null;
  customer_phone: string;
  otp_code: string;
  otp_verified: boolean;
  current_latitude: number | null;
  current_longitude: number | null;
  assigned_at: string | null;
  picked_up_at: string | null;
  delivered_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface MerchantDriver {
  id: string;
  name: string;
  email: string;
  phone_number: string;
  driver_type: string;
  is_available: boolean;
}

export interface MerchantPartner {
  id: string;
  name: string;
  contact_name: string | null;
  phone_number: string;
  address: string | null;
  active: boolean;
  notes: string | null;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit, OnDestroy {
  readonly authService = inject(AuthService);
  private http = inject(HttpClient);
  readonly apiUrl = 'http://localhost:8000';
  private autoRefreshTimer: any = null;

  // Mode de visualisation : 'platform' (Super Admin), 'merchant' (Boutique), 'driver' (Livreur Mobile)
  viewMode = signal<'platform' | 'merchant' | 'driver'>('merchant');

  // Navigation Super Admin (Plateforme)
  activePlatformTab = signal<'overview' | 'businesses' | 'users' | 'health' | 'audit'>('overview');
  platformAuditLogs = signal<PlatformAuditLog[]>([]);
  auditFilterAction = signal<string>('');

  // Navigation Commerçant
  activeTab = signal<'overview' | 'orders' | 'products' | 'deliveries' | 'support'>('overview');

  // Formulaire de connexion
  loginEmail = signal<string>('admin@maliagent.ml');
  loginPassword = signal<string>('');
  loginError = signal<string | null>(null);
  isLoggingIn = signal<boolean>(false);

  // États globaux
  loading = signal<boolean>(false);
  backendConnected = signal<boolean>(true);
  toastMessage = signal<string | null>(null);

  // ================= DONNÉES SUPER ADMIN =================
  platformStats = signal<PlatformStats>({
    businesses: { total: 0, active: 0, suspended: 0 },
    orders: { total_count: 0, total_gmv_fcfa: 0 },
    engagement: { total_customers: 0, total_conversations: 0, total_handoffs: 0 },
    users_count: 0,
  });
  platformBusinesses = signal<PlatformBusiness[]>([]);
  platformUsers = signal<PlatformUser[]>([]);
  platformHealth = signal<PlatformHealth | null>(null);

  // Modales Super Admin
  showCreateBusinessModal = signal<boolean>(false);
  newBusiness = {
    name: '',
    whatsapp_phone_number: '',
    currency: 'XOF',
  };

  showCreateUserModal = signal<boolean>(false);
  newUser = {
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    role: 'admin' as 'super_admin' | 'admin' | 'vendeur' | 'operateur',
    business_id: '',
  };

  // ================= DONNÉES COMMERÇANT =================
  business = signal<BusinessInfo>({
    id: '',
    name: 'MaliAgent Boutique',
    currency: 'XOF',
    whatsapp_phone_number: '15556640413',
  });

  kpis = signal<Kpis>({
    total_revenue: 0,
    today_revenue: 0,
    today_orders_count: 0,
    pending_orders_count: 0,
    total_customers: 0,
    low_stock_count: 0,
    pending_handoffs_count: 0,
  });

  orders = signal<Order[]>([]);
  products = signal<Product[]>([]);
  lowStockProducts = signal<any[]>([]);
  handoffs = signal<any[]>([]);

  // ================= DONNÉES LIVREUR (SPRINT 11) =================
  driverMissions = signal<DriverMission[]>([]);
  driverTab = signal<'active' | 'history'>('active');
  selectedMissionForOtp = signal<DriverMission | null>(null);
  otpInput = signal<string>('');
  isVerifyingOtp = signal<boolean>(false);
  otpError = signal<string | null>(null);

  activeDriverMissions = computed(() =>
    this.driverMissions().filter((m) => m.status !== 'delivered' && m.status !== 'cancelled')
  );

  completedDriverMissions = computed(() =>
    this.driverMissions().filter((m) => m.status === 'delivered')
  );

  // Filtres commerçant
  orderStatusFilter = signal<string>('all');
  orderSearchQuery = signal<string>('');
  productSearchQuery = signal<string>('');

  // Modale Nouveau Produit
  showAddProductModal = signal<boolean>(false);
  newProduct = {
    name: '',
    category: 'téléphone',
    price: 0,
    stock_quantity: 1,
  };

  // Filtrage réactif des commandes
  filteredOrders = computed(() => {
    let list = this.orders();
    const filter = this.orderStatusFilter();
    const query = this.orderSearchQuery().toLowerCase().trim();

    if (filter !== 'all') {
      list = list.filter((o) => o.status === filter);
    }
    if (query) {
      list = list.filter(
        (o) =>
          o.short_id.toLowerCase().includes(query) ||
          o.customer.phone.toLowerCase().includes(query) ||
          (o.delivery_address && o.delivery_address.toLowerCase().includes(query))
      );
    }
    return list;
  });

  // Filtrage réactif des produits
  filteredProducts = computed(() => {
    let list = this.products();
    const query = this.productSearchQuery().toLowerCase().trim();
    if (query) {
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(query) ||
          p.category.toLowerCase().includes(query)
      );
    }
    return list;
  });

  // ================= DONNÉES FLOTTE & LOGISTIQUE COMMERÇANT (SPRINT 12) =================
  merchantMissions = signal<MerchantMission[]>([]);
  merchantDrivers = signal<MerchantDriver[]>([]);
  merchantPartners = signal<MerchantPartner[]>([]);
  deliveryStatusFilter = signal<string>('all');
  deliverySearchQuery = signal<string>('');

  // Modale Attribution de Mission
  showAssignMissionModal = signal<boolean>(false);
  selectedOrderForMission = signal<Order | null>(null);
  assignMissionForm = {
    assignment_type: 'internal' as 'internal' | 'partner',
    driver_id: '',
    partner_id: '',
    pickup_address: '',
    delivery_address: '',
    notes: '',
  };
  isAssigningMission = signal<boolean>(false);

  // Modale Nouveau Partenaire
  showAddPartnerModal = signal<boolean>(false);
  newPartnerForm = {
    name: '',
    contact_name: '',
    phone_number: '',
    address: '',
    notes: '',
  };
  isCreatingPartner = signal<boolean>(false);

  // Filtrage réactif des missions commerçant
  filteredMerchantMissions = computed(() => {
    let list = this.merchantMissions();
    const filter = this.deliveryStatusFilter();
    const query = this.deliverySearchQuery().toLowerCase().trim();

    if (filter !== 'all') {
      list = list.filter((m) => m.status === filter);
    }
    if (query) {
      list = list.filter(
        (m) =>
          (m.customer_phone && m.customer_phone.includes(query)) ||
          (m.customer_name && m.customer_name.toLowerCase().includes(query)) ||
          (m.driver_name && m.driver_name.toLowerCase().includes(query)) ||
          (m.partner_name && m.partner_name.toLowerCase().includes(query)) ||
          (m.delivery_address && m.delivery_address.toLowerCase().includes(query)) ||
          m.id.toLowerCase().includes(query) ||
          m.order_id.toLowerCase().includes(query)
      );
    }
    return list;
  });

  // Métriques KPI Flotte
  deliveryKpis = computed(() => {
    const list = this.merchantMissions();
    return {
      total: list.length,
      pending: list.filter((m) => m.status === 'pending').length,
      in_transit: list.filter((m) => m.status === 'in_transit' || m.status === 'picked_up' || m.status === 'assigned').length,
      delivered: list.filter((m) => m.status === 'delivered').length,
    };
  });

  ngOnInit() {
    if (this.authService.isAuthenticated()) {
      if (this.authService.isSuperAdmin()) {
        this.viewMode.set('platform');
        this.loadPlatformAll();
      } else if (this.authService.isDriver()) {
        this.viewMode.set('driver');
        this.loadDriverMissions();
      } else {
        this.viewMode.set('merchant');
        this.refreshAll();
      }
      this.startAutoRefresh();
    }
  }

  ngOnDestroy() {
    this.stopAutoRefresh();
  }

  private startAutoRefresh() {
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
          if (this.activeTab() === 'deliveries') {
            this.loadMerchantDeliveries();
          }
        }
      }
    }, 15000);
  }

  private stopAutoRefresh() {
    if (this.autoRefreshTimer) {
      clearInterval(this.autoRefreshTimer);
      this.autoRefreshTimer = null;
    }
  }

  // Connexion
  submitLogin() {
    const email = this.loginEmail().trim();
    const password = this.loginPassword();

    if (!email || !password) {
      this.loginError.set('Veuillez renseigner votre email et mot de passe.');
      return;
    }

    this.isLoggingIn.set(true);
    this.loginError.set(null);

    this.authService.login(email, password).subscribe({
      next: (session) => {
        this.isLoggingIn.set(false);
        this.showToast(`Bienvenue, ${session.email} !`);
        this.loginPassword.set('');

        if (this.authService.isSuperAdmin()) {
          this.viewMode.set('platform');
          this.loadPlatformAll();
        } else if (this.authService.isDriver()) {
          this.viewMode.set('driver');
          this.loadDriverMissions();
        } else {
          this.viewMode.set('merchant');
          this.refreshAll();
        }
        this.startAutoRefresh();
      },
      error: (err) => {
        this.isLoggingIn.set(false);
        const detail = err.error?.detail;
        this.loginError.set(
          typeof detail === 'string' ? detail : 'Identifiants invalides ou connexion impossible'
        );
      },
    });
  }

  // Déconnexion
  logout() {
    this.stopAutoRefresh();
    this.authService.logout();
    this.orders.set([]);
    this.products.set([]);
    this.handoffs.set([]);
    this.platformBusinesses.set([]);
    this.platformUsers.set([]);
    this.viewMode.set('merchant');
    this.showToast('Vous avez été déconnecté.');
  }

  // ================= ACTIONS SUPER ADMIN =================

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
        this.platformBusinesses.set(data);
      },
    });
  }

  loadPlatformUsers() {
    this.http.get<PlatformUser[]>(`${this.apiUrl}/api/platform/users`).subscribe({
      next: (data) => {
        this.platformUsers.set(data);
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
        this.platformAuditLogs.set(data);
      },
    });
  }

  submitNewBusiness() {
    if (!this.newBusiness.name || !this.newBusiness.whatsapp_phone_number) {
      this.showToast('Veuillez renseigner le nom et le numéro WhatsApp');
      return;
    }
    this.http.post(`${this.apiUrl}/api/platform/businesses`, this.newBusiness).subscribe({
      next: (created: any) => {
        this.showToast(`Boutique ${created.name} créée avec succès !`);
        this.showCreateBusinessModal.set(false);
        this.newBusiness = { name: '', whatsapp_phone_number: '', currency: 'XOF' };
        this.loadPlatformBusinesses();
        this.loadPlatformStats();
      },
      error: (err) => {
        this.showToast(err.error?.detail || 'Erreur lors de la création de la boutique');
      },
    });
  }

  toggleBusinessStatus(biz: PlatformBusiness) {
    const newStatus = !biz.is_active;
    this.http
      .patch(`${this.apiUrl}/api/platform/businesses/${biz.id}`, { is_active: newStatus })
      .subscribe({
        next: () => {
          this.showToast(
            `Boutique ${biz.name} ${newStatus ? 'réactivée' : 'suspendue'} avec succès`
          );
          this.loadPlatformBusinesses();
          this.loadPlatformStats();
        },
        error: () => {
          this.showToast('Erreur lors du changement de statut');
        },
      });
  }

  submitNewUser() {
    if (!this.newUser.email || !this.newUser.password || !this.newUser.first_name) {
      this.showToast('Veuillez remplir les champs obligatoires');
      return;
    }
    const payload: any = { ...this.newUser };
    if (payload.role === 'super_admin') {
      delete payload.business_id;
    }
    this.http.post(`${this.apiUrl}/api/platform/users`, payload).subscribe({
      next: (created: any) => {
        this.showToast(`Utilisateur ${created.email} créé avec succès !`);
        this.showCreateUserModal.set(false);
        this.newUser = {
          email: '',
          password: '',
          first_name: '',
          last_name: '',
          role: 'admin',
          business_id: '',
        };
        this.loadPlatformUsers();
        this.loadPlatformStats();
      },
      error: (err) => {
        this.showToast(err.error?.detail || "Erreur lors de la création de l'utilisateur");
      },
    });
  }

  toggleUserStatus(u: PlatformUser) {
    const newStatus = !u.is_active;
    this.http
      .patch(`${this.apiUrl}/api/platform/users/${u.id}`, { is_active: newStatus })
      .subscribe({
        next: () => {
          this.showToast(
            `Compte ${u.email} ${newStatus ? 'activé' : 'désactivé'} avec succès`
          );
          this.loadPlatformUsers();
        },
        error: (err) => {
          this.showToast(err.error?.detail || 'Erreur lors de la mise à jour');
        },
      });
  }

  // Inspection d'une boutique spécifique par le Super Admin (Section 15)
  inspectBusiness(biz: PlatformBusiness) {
    this.http
      .post<{
        impersonation_token: string;
        business_id: string;
        business_name: string;
        expires_in_minutes: number;
      }>(`${this.apiUrl}/api/platform/impersonate/${biz.id}`, {})
      .subscribe({
        next: (res) => {
          this.authService.startImpersonation(
            res.impersonation_token,
            res.business_id,
            res.business_name
          );
          this.business.set({
            id: biz.id,
            name: biz.name,
            currency: biz.currency,
            whatsapp_phone_number: biz.whatsapp_phone_number,
          });
          this.viewMode.set('merchant');
          this.activeTab.set('overview');
          this.refreshAll();
          this.showToast(
            `Session d'inspection active (15 min) : ${biz.name} — Actions tracées dans l'audit.`
          );
        },
        error: (err) => {
          this.showToast(err.error?.detail || "Impossible d'inspecter cette boutique");
        },
      });
  }

  returnToPlatform() {
    this.authService.stopImpersonation();
    this.viewMode.set('platform');
    this.loadPlatformAll();
    this.showToast("Session d'impersonation terminée — Retour au cockpit Super Admin");
  }

  // ================= ACTIONS COMMERÇANT =================

  refreshAll() {
    this.loading.set(true);
    this.loadStats();
    this.loadOrders();
    this.loadProducts();
    this.loadHandoffs();
    this.loadMerchantDeliveries();
  }

  loadStats() {
    this.http.get<any>(`${this.apiUrl}/api/dashboard/stats`).subscribe({
      next: (data) => {
        this.business.set(data.business);
        this.kpis.set(data.kpis);
        this.lowStockProducts.set(data.low_stock_products || []);
        this.backendConnected.set(true);
      },
      error: () => {
        this.backendConnected.set(false);
      },
    });
  }

  loadHandoffs() {
    this.http.get<{ handoffs: any[]; total: number }>(`${this.apiUrl}/api/dashboard/handoffs`).subscribe({
      next: (data) => {
        this.handoffs.set(data.handoffs);
      },
    });
  }

  resolveHandoff(convId: string) {
    this.http.post(`${this.apiUrl}/api/dashboard/handoffs/${convId}/resolve`, {}).subscribe({
      next: () => {
        this.showToast("Demande d'assistance résolue : l'agent IA est réactivé !");
        this.loadHandoffs();
        this.loadStats();
      },
      error: () => {
        this.showToast('Erreur lors de la résolution');
      },
    });
  }

  exportCsv() {
    this.http.get(`${this.apiUrl}/api/orders/export-csv`, { responseType: 'blob' }).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `commandes_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
        this.showToast('Export CSV téléchargé avec succès !');
      },
      error: () => {
        this.showToast("Erreur lors de l'export CSV");
      },
    });
  }

  loadOrders() {
    this.http.get<{ orders: Order[]; total: number }>(`${this.apiUrl}/api/orders`).subscribe({
      next: (data) => {
        this.orders.set(data.orders);
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
        this.products.set(data);
      },
    });
  }

  updateOrderStatus(orderId: string, newStatus: string) {
    this.http
      .patch(`${this.apiUrl}/api/orders/${orderId}/status`, { status: newStatus })
      .subscribe({
        next: () => {
          this.showToast(`Commande mise à jour : ${newStatus}`);
          this.loadOrders();
          this.loadStats();
        },
        error: () => {
          this.showToast('Erreur lors de la mise à jour');
        },
      });
  }

  quickAdjustStock(product: Product, delta: number) {
    const newStock = Math.max(0, product.stock_quantity + delta);
    this.http
      .patch(`${this.apiUrl}/api/products/${product.id}`, { stock_quantity: newStock })
      .subscribe({
        next: () => {
          this.showToast(`Stock ajusté pour ${product.name} (${newStock})`);
          this.loadProducts();
          this.loadStats();
        },
      });
  }

  submitNewProduct() {
    if (!this.newProduct.name || this.newProduct.price <= 0) {
      this.showToast('Veuillez renseigner un nom et un prix valide');
      return;
    }
    this.http.post(`${this.apiUrl}/api/products`, this.newProduct).subscribe({
      next: () => {
        this.showToast(`Produit ${this.newProduct.name} ajouté !`);
        this.showAddProductModal.set(false);
        this.newProduct = { name: '', category: 'téléphone', price: 0, stock_quantity: 1 };
        this.loadProducts();
        this.loadStats();
      },
    });
  }

  openInvoice(downloadUrl: string | null) {
    if (downloadUrl) {
      window.open(`${this.apiUrl}${downloadUrl}`, '_blank');
    }
  }

  showToast(msg: string) {
    this.toastMessage.set(msg);
    setTimeout(() => {
      this.toastMessage.set(null);
    }, 3500);
  }

  formatFcfa(val: number | null | undefined): string {
    if (val === null || val === undefined) return '0 FCFA';
    return `${val.toLocaleString('fr-FR')} FCFA`;
  }

  // ================= MÉTHODES LIVREUR MOBILE (SPRINT 11) =================

  loadDriverMissions() {
    this.http
      .get<{ missions: DriverMission[]; total: number }>(`${this.apiUrl}/api/delivery/driver/missions`)
      .subscribe({
        next: (res) => {
          this.driverMissions.set(res.missions || []);
        },
        error: (err) => {
          console.error('Erreur chargement missions livreur', err);
        },
      });
  }

  acceptMission(m: DriverMission) {
    this.http.post(`${this.apiUrl}/api/delivery/driver/missions/${m.id}/accept`, {}).subscribe({
      next: () => {
        this.showToast('Course acceptée !');
        this.loadDriverMissions();
      },
      error: () => {
        this.showToast("Erreur lors de l'acceptation de la course");
      },
    });
  }

  pickupMission(m: DriverMission) {
    this.http.post(`${this.apiUrl}/api/delivery/driver/missions/${m.id}/pickup`, {}).subscribe({
      next: () => {
        this.showToast('Colis récupéré en boutique !');
        this.loadDriverMissions();
      },
      error: () => {
        this.showToast('Erreur lors de la récupération du colis');
      },
    });
  }

  startRouteMission(m: DriverMission) {
    this.http.post(`${this.apiUrl}/api/delivery/driver/missions/${m.id}/start-route`, {}).subscribe({
      next: () => {
        this.showToast('En route vers le client !');
        this.loadDriverMissions();
      },
      error: () => {
        this.showToast('Erreur lors du départ en route');
      },
    });
  }

  updateGpsLocation(m: DriverMission) {
    if (!navigator.geolocation) {
      this.showToast("La géolocalisation n'est pas supportée par votre navigateur");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const payload = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
        this.http.post(`${this.apiUrl}/api/delivery/driver/missions/${m.id}/location`, payload).subscribe({
          next: () => {
            this.showToast('Position GPS actualisée avec succès');
            this.loadDriverMissions();
          },
          error: () => {
            this.showToast("Erreur lors de l'actualisation GPS");
          },
        });
      },
      () => {
        this.showToast('Impossible de récupérer la position GPS (activez le GPS)');
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  openOtpModal(m: DriverMission) {
    this.selectedMissionForOtp.set(m);
    this.otpInput.set('');
    this.otpError.set(null);
  }

  closeOtpModal() {
    this.selectedMissionForOtp.set(null);
    this.otpInput.set('');
    this.otpError.set(null);
  }

  appendOtpDigit(digit: string) {
    if (this.otpInput().length < 6) {
      this.otpInput.set(this.otpInput() + digit);
      this.otpError.set(null);
    }
  }

  deleteOtpDigit() {
    const cur = this.otpInput();
    if (cur.length > 0) {
      this.otpInput.set(cur.slice(0, -1));
      this.otpError.set(null);
    }
  }

  clearOtpInput() {
    this.otpInput.set('');
    this.otpError.set(null);
  }

  submitOtpVerification() {
    const mission = this.selectedMissionForOtp();
    const code = this.otpInput().trim();
    if (!mission || code.length !== 6) {
      this.otpError.set('Veuillez saisir les 6 chiffres du code OTP');
      return;
    }

    this.isVerifyingOtp.set(true);
    this.otpError.set(null);

    this.http
      .post(`${this.apiUrl}/api/delivery/driver/missions/${mission.id}/verify-otp`, { otp_code: code })
      .subscribe({
        next: () => {
          this.isVerifyingOtp.set(false);
          this.showToast('🎉 Livraison validée avec succès !');
          this.closeOtpModal();
          this.loadDriverMissions();
        },
        error: (err) => {
          this.isVerifyingOtp.set(false);
          const detail = err.error?.detail || 'Code OTP incorrect. Veuillez vérifier avec le client.';
          this.otpError.set(detail);
        },
      });
  }

  // ================= ACTIONS FLOTTE & LOGISTIQUE COMMERÇANT (SPRINT 12) =================

  loadMerchantDeliveries() {
    this.http.get<{ missions: MerchantMission[]; total: number }>(`${this.apiUrl}/api/delivery/missions`).subscribe({
      next: (data) => {
        this.merchantMissions.set(data.missions || []);
      },
      error: () => {},
    });

    this.http.get<MerchantDriver[]>(`${this.apiUrl}/api/delivery/drivers`).subscribe({
      next: (drivers) => {
        this.merchantDrivers.set(drivers || []);
      },
      error: () => {},
    });

    this.http.get<MerchantPartner[]>(`${this.apiUrl}/api/delivery/partners`).subscribe({
      next: (partners) => {
        this.merchantPartners.set(partners || []);
      },
      error: () => {},
    });
  }

  openAssignMissionModal(order: Order) {
    this.selectedOrderForMission.set(order);
    this.assignMissionForm = {
      assignment_type: 'internal',
      driver_id: this.merchantDrivers().length > 0 ? this.merchantDrivers()[0].id : '',
      partner_id: this.merchantPartners().length > 0 ? this.merchantPartners()[0].id : '',
      pickup_address: 'Boutique Principale Bamako',
      delivery_address: order.delivery_address || 'Bamako',
      notes: `Commande #${order.short_id}`,
    };
    this.showAssignMissionModal.set(true);
  }

  submitAssignMission() {
    const order = this.selectedOrderForMission();
    if (!order) return;

    const payload: any = {
      order_id: order.id,
      assignment_type: this.assignMissionForm.assignment_type,
      pickup_address: this.assignMissionForm.pickup_address,
      delivery_address: this.assignMissionForm.delivery_address,
      customer_name: order.customer.name || 'Client WhatsApp',
      customer_phone: order.customer.phone,
      notes: this.assignMissionForm.notes,
    };

    if (this.assignMissionForm.assignment_type === 'internal') {
      if (!this.assignMissionForm.driver_id) {
        this.showToast('Veuillez sélectionner un coursier interne');
        return;
      }
      payload.driver_id = this.assignMissionForm.driver_id;
    } else {
      if (!this.assignMissionForm.partner_id) {
        this.showToast('Veuillez sélectionner un partenaire logistique');
        return;
      }
      payload.partner_id = this.assignMissionForm.partner_id;
    }

    this.isAssigningMission.set(true);
    this.http.post(`${this.apiUrl}/api/delivery/missions`, payload).subscribe({
      next: (res: any) => {
        this.isAssigningMission.set(false);
        this.showAssignMissionModal.set(false);
        this.selectedOrderForMission.set(null);
        this.showToast(`Mission #${res.id?.slice(0, 8)} créée et assignée avec succès ! (Code OTP: ${res.otp_code})`);
        this.loadMerchantDeliveries();
        this.loadOrders();
      },
      error: (err) => {
        this.isAssigningMission.set(false);
        this.showToast(err.error?.detail || "Erreur lors de l'assignation de la livraison");
      },
    });
  }

  openAddPartnerModal() {
    this.newPartnerForm = {
      name: '',
      contact_name: '',
      phone_number: '',
      address: '',
      notes: '',
    };
    this.showAddPartnerModal.set(true);
  }

  submitAddPartner() {
    if (!this.newPartnerForm.name || !this.newPartnerForm.phone_number) {
      this.showToast('Veuillez renseigner le nom et le numéro de téléphone');
      return;
    }

    this.isCreatingPartner.set(true);
    this.http.post(`${this.apiUrl}/api/delivery/partners`, this.newPartnerForm).subscribe({
      next: () => {
        this.isCreatingPartner.set(false);
        this.showAddPartnerModal.set(false);
        this.showToast(`Partenaire ${this.newPartnerForm.name} ajouté avec succès !`);
        this.loadMerchantDeliveries();
      },
      error: (err) => {
        this.isCreatingPartner.set(false);
        this.showToast(err.error?.detail || "Erreur lors de l'enregistrement du partenaire");
      },
    });
  }

  copyTrackingLink(orderId: string) {
    const url = `${this.apiUrl}/api/delivery/track/${orderId}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(
        () => this.showToast('📋 Lien de suivi copié dans le presse-papier !'),
        () => this.showToast(`Lien de suivi : ${url}`)
      );
    } else {
      this.showToast(`Lien de suivi : ${url}`);
    }
  }

  openPublicTracking(orderId: string) {
    window.open(`${this.apiUrl}/api/delivery/track/${orderId}`, '_blank');
  }
}
