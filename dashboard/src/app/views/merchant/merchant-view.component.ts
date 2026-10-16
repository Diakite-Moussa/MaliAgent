import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { AuthService } from '../../auth.service';
import { DashboardStateService } from '../../services/dashboard-state.service';
import {
  Order,
  Product,
  ProductCategory,
  ProductVariant,
  MerchantMission,
  HandoffConversation,
  KnowledgeDocument,
} from '../../models/dashboard.models';

@Component({
  selector: 'app-merchant-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './merchant-view.component.html',
})
export class MerchantViewComponent implements OnInit {
  readonly state = inject(DashboardStateService);
  readonly authService = inject(AuthService);
  private http = inject(HttpClient);
  private router = inject(Router);

  // Navigation Commerçant
  activeTab = signal<'overview' | 'orders' | 'products' | 'deliveries' | 'payments' | 'support' | 'agent'>('overview');

  // Filtres commandes
  orderStatusFilter = signal<string>('all');
  orderSearchQuery = signal<string>('');

  // Filtres produits
  productSearchQuery = signal<string>('');
  selectedCategoryFilter = signal<string>('all');
  expandedProductIds = signal<Set<string>>(new Set<string>());

  // Gestion des Catégories
  showAddCategoryModal = signal<boolean>(false);
  isSavingCategory = signal<boolean>(false);
  newCategory = {
    name: '',
    description: '',
  };

  // Filtres livraisons & flotte
  deliveryStatusFilter = signal<string>('all');
  deliverySearchQuery = signal<string>('');

  // Filtres paiements
  paymentStatusFilter = signal<string>('all');
  paymentProviderFilter = signal<string>('all');
  paymentSearchQuery = signal<string>('');

  // Support & Relais Humains
  selectedHandoff = signal<HandoffConversation | null>(null);
  handoffReplyText = signal<string>('');
  isSendingHandoffReply = signal<boolean>(false);

  // Modale Nouveau Produit
  showAddProductModal = signal<boolean>(false);
  isUploadingProductImage = signal<boolean>(false);
  newProductHasVariants = signal<boolean>(false);
  newProduct = {
    name: '',
    category_id: '',
    category: 'Général',
    price: 0,
    stock_quantity: 1,
    image_url: '',
    variants: [] as ProductVariant[],
  };

  // Modale Modifier Produit
  showEditProductModal = signal<boolean>(false);
  isUploadingEditProductImage = signal<boolean>(false);
  isSavingEditProduct = signal<boolean>(false);
  editProductHasVariants = signal<boolean>(false);
  editProduct = {
    id: '',
    name: '',
    category_id: '',
    category: 'Général',
    price: 0,
    stock_quantity: 0,
    image_url: '',
    variants: [] as ProductVariant[],
  };

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

  // Modale Nouveau Livreur Interne
  showAddDriverModal = signal<boolean>(false);
  newDriverForm = {
    first_name: '',
    last_name: '',
    phone_number: '',
    email: '',
    password: '',
    driver_type: 'internal' as 'internal' | 'partner',
  };
  isCreatingDriver = signal<boolean>(false);

  // Proxies réactifs vers le state global
  readonly business = this.state.business;
  readonly kpis = this.state.kpis;
  readonly orders = this.state.orders;
  readonly products = this.state.products;
  readonly categories = this.state.categories;
  readonly lowStockProducts = this.state.lowStockProducts;
  readonly handoffs = this.state.handoffs;
  readonly payments = this.state.payments;
  readonly merchantMissions = this.state.merchantMissions;
  readonly merchantDrivers = this.state.merchantDrivers;
  readonly merchantPartners = this.state.merchantPartners;
  readonly agentConfig = this.state.agentConfig;
  readonly isSavingAgentConfig = this.state.isSavingAgentConfig;
  readonly knowledgeDocuments = this.state.knowledgeDocuments;
  readonly backendConnected = this.state.backendConnected;
  readonly loading = this.state.loading;

  // Base de Connaissances (RAG)
  isUploadingKnowledge = signal<boolean>(false);
  isDeletingKnowledgeId = signal<string | null>(null);

  // Formulaire de configuration Agent IA
  agentForm = {
    agent_name: 'Assistant',
    tone: 'chaleureux',
    default_language: 'fr',
    custom_rules: '',
    welcome_message: '',
    enabled: true,
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
    const catFilter = this.selectedCategoryFilter();

    if (catFilter !== 'all') {
      list = list.filter(
        (p) =>
          (p.category_id && p.category_id === catFilter) ||
          p.category.toLowerCase() === catFilter.toLowerCase()
      );
    }

    if (query) {
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(query) ||
          p.category.toLowerCase().includes(query) ||
          (p.variants &&
            p.variants.some(
              (v) =>
                v.value.toLowerCase().includes(query) ||
                v.name.toLowerCase().includes(query)
            ))
      );
    }
    return list;
  });

  // Filtrage réactif des missions
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

  deliveryKpis = computed(() => {
    const list = this.merchantMissions();
    return {
      total: list.length,
      pending: list.filter((m) => m.status === 'pending').length,
      in_transit: list.filter((m) => m.status === 'in_transit' || m.status === 'picked_up' || m.status === 'assigned').length,
      delivered: list.filter((m) => m.status === 'delivered').length,
    };
  });

  filteredPayments = computed(() => {
    let list = this.payments();
    const sFilter = this.paymentStatusFilter();
    const pFilter = this.paymentProviderFilter();
    const query = this.paymentSearchQuery().toLowerCase().trim();

    if (sFilter !== 'all') {
      list = list.filter((p) => p.status === sFilter);
    }
    if (pFilter !== 'all') {
      list = list.filter((p) => p.provider.toLowerCase().includes(pFilter.toLowerCase()));
    }
    if (query) {
      list = list.filter(
        (p) =>
          p.transaction_reference.toLowerCase().includes(query) ||
          p.order_id.toLowerCase().includes(query) ||
          (p.customer_phone && p.customer_phone.includes(query))
      );
    }
    return list;
  });

  paymentKpis = computed(() => {
    const list = this.payments();
    const successPayments = list.filter((p) => p.status === 'success');
    const totalCollected = successPayments.reduce((acc, curr) => acc + Number(curr.amount || 0), 0);
    return {
      total: list.length,
      success_count: successPayments.length,
      pending_count: list.filter((p) => p.status === 'pending_validation' || p.status === 'initiated').length,
      failed_count: list.filter((p) => p.status === 'failed' || p.status === 'expired').length,
      total_collected: totalCollected,
    };
  });

  ngOnInit() {
    this.refreshAll();
    setTimeout(() => this.initAgentForm(), 600);
  }

  refreshAll() {
    this.state.refreshMerchantAll();
    setTimeout(() => this.initAgentForm(), 600);
  }

  loadOrders() {
    this.state.loadOrders();
  }

  loadStats() {
    this.state.loadStats();
  }

  loadProducts() {
    this.state.loadProducts();
  }

  loadHandoffs() {
    this.state.loadHandoffs();
  }

  loadMerchantDeliveries() {
    this.state.loadMerchantDeliveries();
  }

  loadPayments() {
    this.state.loadPayments();
  }

  formatFcfa(val: number | null | undefined): string {
    if (val === null || val === undefined) return '0 FCFA';
    return Number(val).toLocaleString('fr-FR') + ' FCFA';
  }

  openInvoice(url: string | null) {
    if (url) {
      window.open(url, '_blank');
    }
  }

  simulatePayment(payment: any, targetStatus: 'success' | 'failed') {
    this.http
      .post(`${this.state.apiUrl}/api/payments/simulate-webhook`, {
        transaction_reference: payment.transaction_reference,
        target_status: targetStatus,
      })
      .subscribe({
        next: () => {
          this.state.showToast(`Paiement simulé (${targetStatus}) avec succès !`);
          this.loadPayments();
          this.loadOrders();
          this.loadStats();
        },
        error: () => {
          this.state.showToast('Erreur lors de la simulation');
        },
      });
  }

  submitNewProduct() {
    this.submitAddProduct();
  }

  updateOrderStatus(orderId: string, newStatus: string) {
    this.http
      .patch(`${this.state.apiUrl}/api/orders/${orderId}/status`, { status: newStatus })
      .subscribe({
        next: () => {
          this.state.showToast(`Commande mise à jour : ${newStatus}`);
          this.state.loadOrders();
          this.state.loadStats();
        },
        error: () => {
          this.state.showToast('Erreur lors de la mise à jour');
        },
      });
  }

  quickAdjustStock(product: Product, delta: number) {
    const newQty = Math.max(0, product.stock_quantity + delta);
    this.http
      .patch(`${this.state.apiUrl}/api/products/${product.id}/stock`, { stock_quantity: newQty })
      .subscribe({
        next: () => {
          this.state.showToast(`Stock de ${product.name} mis à jour : ${newQty}`);
          this.state.loadProducts();
          this.state.loadStats();
        },
        error: () => {
          this.state.showToast('Erreur lors de la mise à jour du stock');
        },
      });
  }

  onProductImageSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];

    if (file.size > 5 * 1024 * 1024) {
      this.state.showToast("La taille de l'image ne doit pas dépasser 5 Mo");
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    this.isUploadingProductImage.set(true);
    this.http.post<{ image_url: string; filename: string }>(
      `${this.state.apiUrl}/api/products/upload-image`,
      formData
    ).subscribe({
      next: (res) => {
        this.newProduct.image_url = res.image_url;
        this.isUploadingProductImage.set(false);
        this.state.showToast('✓ Photo du produit uploadée avec succès !');
      },
      error: (err) => {
        this.isUploadingProductImage.set(false);
        this.state.showToast(err.error?.detail || "Erreur lors de l'upload de l'image");
      },
    });
  }

  removeProductImage() {
    this.newProduct.image_url = '';
  }

  // ================= GESTION CATÉGORIES & VARIANTES =================
  toggleProductExpand(productId: string) {
    const s = new Set(this.expandedProductIds());
    if (s.has(productId)) {
      s.delete(productId);
    } else {
      s.add(productId);
    }
    this.expandedProductIds.set(s);
  }

  isProductExpanded(productId: string): boolean {
    return this.expandedProductIds().has(productId);
  }

  openAddCategoryModal() {
    this.newCategory = { name: '', description: '' };
    this.showAddCategoryModal.set(true);
  }

  submitCreateCategory() {
    const name = this.newCategory.name.trim();
    if (!name) {
      this.state.showToast('Veuillez saisir un nom pour la catégorie');
      return;
    }
    this.isSavingCategory.set(true);
    this.http.post<ProductCategory>(`${this.state.apiUrl}/api/categories`, {
      name,
      description: this.newCategory.description.trim() || null,
    }).subscribe({
      next: (res) => {
        this.isSavingCategory.set(false);
        this.state.showToast(`✓ Catégorie "${res.name}" créée avec succès !`);
        this.showAddCategoryModal.set(false);
        this.state.loadCategories();
      },
      error: (err) => {
        this.isSavingCategory.set(false);
        this.state.showToast(err.error?.detail || "Erreur lors de la création de la catégorie");
      },
    });
  }

  addVariant(target: 'new' | 'edit') {
    const newVar: ProductVariant = {
      name: 'Option',
      value: '',
      price: null,
      stock_quantity: 1,
    };
    if (target === 'new') {
      this.newProduct.variants.push(newVar);
    } else {
      this.editProduct.variants.push(newVar);
    }
  }

  removeVariant(target: 'new' | 'edit', index: number) {
    if (target === 'new') {
      this.newProduct.variants.splice(index, 1);
    } else {
      this.editProduct.variants.splice(index, 1);
    }
  }

  quickAdjustVariantStock(product: Product, variant: ProductVariant, delta: number) {
    if (!variant.id) return;
    const newQty = Math.max(0, variant.stock_quantity + delta);
    this.http
      .patch(`${this.state.apiUrl}/api/products/${product.id}/variants/${variant.id}/stock`, {
        stock_quantity: newQty,
      })
      .subscribe({
        next: () => {
          this.state.showToast(`Stock de ${product.name} (${variant.value}) : ${newQty}`);
          this.state.loadProducts();
          this.state.loadStats();
        },
        error: () => {
          this.state.showToast("Erreur lors de l'ajustement du stock de la variante");
        },
      });
  }

  submitAddProduct() {
    if (!this.newProduct.name || this.newProduct.price <= 0) {
      this.state.showToast('Veuillez renseigner le nom et un prix valide');
      return;
    }
    const payload: any = {
      name: this.newProduct.name.trim(),
      category: this.newProduct.category.trim(),
      category_id: this.newProduct.category_id || null,
      price: this.newProduct.price,
      stock_quantity: this.newProduct.stock_quantity,
      image_url: this.newProduct.image_url?.trim() || null,
    };

    if (this.newProductHasVariants() && this.newProduct.variants.length > 0) {
      payload.variants = this.newProduct.variants
        .map((v) => ({
          name: v.name.trim() || 'Option',
          value: v.value.trim(),
          price: v.price && v.price > 0 ? v.price : null,
          stock_quantity: v.stock_quantity || 0,
          sku: v.sku?.trim() || null,
        }))
        .filter((v) => v.value.length > 0);
    }

    this.http.post(`${this.state.apiUrl}/api/products`, payload).subscribe({
      next: (created: any) => {
        this.state.showToast(`Produit ${created.name} ajouté au catalogue !`);
        this.showAddProductModal.set(false);
        this.newProduct = {
          name: '',
          category_id: '',
          category: 'Général',
          price: 0,
          stock_quantity: 1,
          image_url: '',
          variants: [],
        };
        this.newProductHasVariants.set(false);
        this.state.loadProducts();
        this.state.loadCategories();
        this.state.loadStats();
      },
      error: (err) => {
        this.state.showToast(err.error?.detail || "Erreur lors de l'ajout du produit");
      },
    });
  }

  // ================= MÉTHODES ÉDITION PRODUIT =================
  openEditProductModal(product: Product) {
    const hasVars = (product.variants && product.variants.length > 0) || false;
    this.editProductHasVariants.set(hasVars);
    this.editProduct = {
      id: product.id,
      name: product.name,
      category: product.category,
      category_id: product.category_id || '',
      price: product.price,
      stock_quantity: product.stock_quantity,
      image_url: product.image_url || '',
      variants: product.variants ? product.variants.map((v) => ({ ...v })) : [],
    };
    this.showEditProductModal.set(true);
  }

  onEditProductImageSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];

    if (file.size > 5 * 1024 * 1024) {
      this.state.showToast("La taille de l'image ne doit pas dépasser 5 Mo");
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    this.isUploadingEditProductImage.set(true);
    this.http.post<{ image_url: string; filename: string }>(
      `${this.state.apiUrl}/api/products/upload-image`,
      formData
    ).subscribe({
      next: (res) => {
        this.editProduct.image_url = res.image_url;
        this.isUploadingEditProductImage.set(false);
        this.state.showToast('✓ Photo du produit mise à jour !');
      },
      error: (err) => {
        this.isUploadingEditProductImage.set(false);
        this.state.showToast(err.error?.detail || "Erreur lors de l'upload de l'image");
      },
    });
  }

  removeEditProductImage() {
    this.editProduct.image_url = '';
  }

  submitEditProduct() {
    if (!this.editProduct.name || this.editProduct.price < 0) {
      this.state.showToast('Veuillez renseigner un nom et un prix valide');
      return;
    }

    this.isSavingEditProduct.set(true);
    const payload: any = {
      name: this.editProduct.name.trim(),
      category: this.editProduct.category.trim(),
      category_id: this.editProduct.category_id || null,
      price: this.editProduct.price,
      image_url: this.editProduct.image_url?.trim() || null,
    };

    if (this.editProductHasVariants()) {
      payload.variants = this.editProduct.variants
        .map((v) => ({
          id: v.id || null,
          name: v.name.trim() || 'Option',
          value: v.value.trim(),
          price: v.price && v.price > 0 ? v.price : null,
          stock_quantity: v.stock_quantity || 0,
          sku: v.sku?.trim() || null,
        }))
        .filter((v) => v.value.length > 0);
    } else {
      payload.variants = [];
    }

    this.http.patch(`${this.state.apiUrl}/api/products/${this.editProduct.id}`, payload).subscribe({
      next: (updated: any) => {
        this.isSavingEditProduct.set(false);
        this.state.showToast(`✓ Produit "${updated.name}" modifié avec succès !`);
        this.showEditProductModal.set(false);
        this.state.loadProducts();
        this.state.loadCategories();
        this.state.loadStats();
      },
      error: (err) => {
        this.isSavingEditProduct.set(false);
        this.state.showToast(err.error?.detail || "Erreur lors de la modification du produit");
      },
    });
  }

  getProductImageUrl(url: string | null | undefined): string {
    if (!url) return '';
    const trimmed = url.trim();
    if (trimmed.includes('/api/products/images/')) {
      const filename = trimmed.split('/api/products/images/').pop();
      return `${this.state.apiUrl}/api/products/images/${filename}`;
    }
    return trimmed;
  }

  // ================= MÉTHODES CONFIGURATION AGENT IA =================
  initAgentForm() {
    const cfg = this.agentConfig();
    if (cfg) {
      this.agentForm = {
        agent_name: cfg.agent_name || 'Assistant',
        tone: cfg.tone || 'chaleureux',
        default_language: cfg.default_language || 'fr',
        custom_rules: cfg.custom_rules || '',
        welcome_message: cfg.welcome_message || '',
        enabled: cfg.enabled !== undefined ? cfg.enabled : true,
      };
    }
  }

  loadAgentConfig() {
    this.state.loadAgentConfig();
    this.state.loadKnowledgeDocuments();
    setTimeout(() => this.initAgentForm(), 300);
  }

  saveAgentConfig() {
    const payload = {
      agent_name: this.agentForm.agent_name.trim() || 'Assistant',
      tone: this.agentForm.tone,
      default_language: this.agentForm.default_language,
      custom_rules: this.agentForm.custom_rules?.trim() || null,
      welcome_message: this.agentForm.welcome_message?.trim() || null,
      enabled: this.agentForm.enabled,
    };
    this.state.updateAgentConfig(payload);
  }

  toggleAgentEnabled() {
    this.agentForm.enabled = !this.agentForm.enabled;
    this.saveAgentConfig();
  }

  setTone(tone: string) {
    this.agentForm.tone = tone;
  }

  setLanguage(lang: string) {
    this.agentForm.default_language = lang;
  }

  // ================= MÉTHODES BASE DE CONNAISSANCES (RAG) =================
  onKnowledgeFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;

    const file = input.files[0];
    const allowedExtensions = ['pdf', 'txt'];
    const ext = file.name.split('.').pop()?.toLowerCase() || '';

    if (!allowedExtensions.includes(ext)) {
      this.state.showToast('Format non supporté. Veuillez sélectionner un fichier PDF ou TXT.');
      input.value = '';
      return;
    }

    if (file.size > 15 * 1024 * 1024) {
      this.state.showToast('Le fichier est trop volumineux (maximum 15 Mo).');
      input.value = '';
      return;
    }

    this.isUploadingKnowledge.set(true);
    this.state.uploadKnowledgeDocument(file).subscribe({
      next: (doc) => {
        this.isUploadingKnowledge.set(false);
        input.value = '';
        this.state.showToast(`✓ Document « ${doc.filename} » indexé dans la base de connaissances !`);
        this.state.loadKnowledgeDocuments();
      },
      error: (err) => {
        this.isUploadingKnowledge.set(false);
        input.value = '';
        const msg = err.error?.detail || "Erreur lors de l'upload et de l'indexation du document";
        this.state.showToast(msg);
      },
    });
  }

  deleteKnowledgeDocument(doc: KnowledgeDocument) {
    if (!confirm(`Supprimer le document « ${doc.filename} » et ses données vectorielles de la base de connaissances ?`)) {
      return;
    }

    this.isDeletingKnowledgeId.set(doc.id);
    this.state.deleteKnowledgeDocument(doc.id).subscribe({
      next: () => {
        this.isDeletingKnowledgeId.set(null);
        this.state.showToast(`✓ Document « ${doc.filename} » supprimé.`);
        this.state.loadKnowledgeDocuments();
      },
      error: (err) => {
        this.isDeletingKnowledgeId.set(null);
        const msg = err.error?.detail || 'Erreur lors de la suppression du document';
        this.state.showToast(msg);
      },
    });
  }

  selectHandoff(conv: HandoffConversation) {
    this.selectedHandoff.set(conv);
    this.handoffReplyText.set('');
  }

  sendHandoffReply() {
    const conv = this.selectedHandoff();
    const msg = this.handoffReplyText().trim();
    if (!conv || !msg) return;

    this.isSendingHandoffReply.set(true);
    this.http.post<{ status: string; message_id: string; content: string; created_at: string }>(
      `${this.state.apiUrl}/api/dashboard/handoffs/${conv.id}/reply`,
      { message: msg }
    ).subscribe({
      next: (res) => {
        this.isSendingHandoffReply.set(false);
        this.handoffReplyText.set('');
        this.state.showToast('✓ Réponse envoyée sur WhatsApp au client !');
        // Mise à jour immédiate du fil de discussion local
        const updated: HandoffConversation = {
          ...conv,
          messages: [
            ...conv.messages,
            {
              id: res.message_id || String(Date.now()),
              role: 'assistant',
              content: res.content || msg,
              created_at: res.created_at || new Date().toISOString(),
            },
          ],
        };
        this.selectedHandoff.set(updated);
        this.state.loadHandoffs();
      },
      error: (err) => {
        this.isSendingHandoffReply.set(false);
        this.state.showToast(err.error?.detail || "Erreur lors de l'envoi WhatsApp");
      },
    });
  }

  resolveHandoff(convId: string) {
    this.http.post(`${this.state.apiUrl}/api/dashboard/handoffs/${convId}/resolve`, {}).subscribe({
      next: () => {
        this.state.showToast("Demande d'assistance résolue : l'agent IA est réactivé !");
        if (this.selectedHandoff()?.id === convId) {
          this.selectedHandoff.set(null);
        }
        this.state.loadHandoffs();
        this.state.loadStats();
      },
      error: () => {
        this.state.showToast('Erreur lors de la résolution');
      },
    });
  }

  openWhatsAppDirect(phone: string) {
    const clean = (phone || '').replace(/[^0-9]/g, '');
    if (clean) {
      window.open(`https://wa.me/${clean}`, '_blank');
    }
  }

  exportCsv() {
    this.http.get(`${this.state.apiUrl}/api/orders/export-csv`, { responseType: 'blob' }).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `commandes_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
        this.state.showToast('Export CSV téléchargé avec succès !');
      },
      error: () => {
        this.state.showToast("Erreur lors de l'export CSV");
      },
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

    if (this.assignMissionForm.assignment_type === 'internal') {
      if (!this.assignMissionForm.driver_id) {
        this.state.showToast('Veuillez sélectionner un coursier interne');
        return;
      }
    } else {
      if (!this.assignMissionForm.partner_id) {
        this.state.showToast('Veuillez sélectionner un partenaire logistique');
        return;
      }
    }

    // Vérifier s'il existe déjà une mission pour cette commande
    const existingMission = this.merchantMissions().find((m) => m.order_id === order.id);

    this.isAssigningMission.set(true);

    if (existingMission) {
      // Mission existante → PATCH /missions/{id}/assign pour réattribuer
      const patchPayload: any = {
        assignment_type: this.assignMissionForm.assignment_type,
        notes: this.assignMissionForm.notes,
      };
      if (this.assignMissionForm.assignment_type === 'internal') {
        patchPayload.driver_id = this.assignMissionForm.driver_id;
      } else {
        patchPayload.partner_id = this.assignMissionForm.partner_id;
      }

      this.http.patch(`${this.state.apiUrl}/api/delivery/missions/${existingMission.id}/assign`, patchPayload).subscribe({
        next: (res: any) => {
          this.isAssigningMission.set(false);
          this.showAssignMissionModal.set(false);
          this.selectedOrderForMission.set(null);
          this.state.showToast(`✓ Mission réattribuée avec succès !`);
          this.state.loadMerchantDeliveries();
          this.state.loadOrders();
        },
        error: (err) => {
          this.isAssigningMission.set(false);
          this.state.showToast(err.error?.detail || "Erreur lors de la réattribution de la mission");
        },
      });
    } else {
      // Pas de mission existante → POST /missions pour en créer une nouvelle
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
        payload.driver_id = this.assignMissionForm.driver_id;
      } else {
        payload.partner_id = this.assignMissionForm.partner_id;
      }

      this.http.post(`${this.state.apiUrl}/api/delivery/missions`, payload).subscribe({
        next: (res: any) => {
          this.isAssigningMission.set(false);
          this.showAssignMissionModal.set(false);
          this.selectedOrderForMission.set(null);
          this.state.showToast(`✓ Mission #${res.id?.slice(0, 8)} créée ! Code OTP: ${res.otp_code}`);
          this.state.loadMerchantDeliveries();
          this.state.loadOrders();
        },
        error: (err) => {
          this.isAssigningMission.set(false);
          this.state.showToast(err.error?.detail || "Erreur lors de la création de la mission");
        },
      });
    }
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
    if (!this.newPartnerForm.name?.trim() || !this.newPartnerForm.phone_number?.trim()) {
      this.state.showToast('Veuillez renseigner le nom et le numéro de téléphone');
      return;
    }

    const payload = {
      name: this.newPartnerForm.name.trim(),
      contact_name: this.newPartnerForm.contact_name?.trim() || null,
      phone_number: this.newPartnerForm.phone_number.trim(),
      address: this.newPartnerForm.address?.trim() || null,
      notes: this.newPartnerForm.notes?.trim() || null,
    };

    this.isCreatingPartner.set(true);
    this.http.post(`${this.state.apiUrl}/api/delivery/partners`, payload).subscribe({
      next: () => {
        this.isCreatingPartner.set(false);
        this.showAddPartnerModal.set(false);
        this.state.showToast(`Partenaire ${payload.name} ajouté avec succès !`);
        this.state.loadMerchantDeliveries();
      },
      error: (err) => {
        this.isCreatingPartner.set(false);
        this.state.showToast(err.error?.detail || "Erreur lors de l'enregistrement du partenaire");
      },
    });
  }

  openAddDriverModal() {
    this.newDriverForm = {
      first_name: '',
      last_name: '',
      phone_number: '',
      email: '',
      password: '',
      driver_type: 'internal',
    };
    this.showAddDriverModal.set(true);
  }

  submitAddDriver() {
    if (!this.newDriverForm.first_name?.trim() || !this.newDriverForm.last_name?.trim() || !this.newDriverForm.phone_number?.trim()) {
      this.state.showToast('Veuillez renseigner le prénom, le nom et le numéro de téléphone');
      return;
    }

    const payload = {
      first_name: this.newDriverForm.first_name.trim(),
      last_name: this.newDriverForm.last_name.trim(),
      phone_number: this.newDriverForm.phone_number.trim(),
      email: this.newDriverForm.email?.trim() || null,
      password: this.newDriverForm.password?.trim() || null,
      driver_type: this.newDriverForm.driver_type,
    };

    this.isCreatingDriver.set(true);
    this.http.post(`${this.state.apiUrl}/api/delivery/drivers`, payload).subscribe({
      next: (res: any) => {
        this.isCreatingDriver.set(false);
        this.showAddDriverModal.set(false);
        this.state.showToast(`Livreur ${res.name} créé avec succès ! Identifiants enregistrés.`);
        this.state.loadMerchantDeliveries();
      },
      error: (err) => {
        this.isCreatingDriver.set(false);
        this.state.showToast(err.error?.detail || "Erreur lors de la création du livreur");
      },
    });
  }

  toggleDriverAvailability(driverId: string, currentStatus: boolean) {
    const newStatus = !currentStatus;
    this.http
      .patch(`${this.state.apiUrl}/api/delivery/drivers/${driverId}`, { is_available: newStatus })
      .subscribe({
        next: () => {
          this.state.showToast(`Statut livreur mis à jour : ${newStatus ? 'En service' : 'En pause'}`);
          this.state.loadMerchantDeliveries();
        },
        error: () => {
          this.state.showToast('Erreur lors de la mise à jour du statut');
        },
      });
  }

  deactivateDriver(driverId: string, driverName: string) {
    if (!confirm(`Êtes-vous sûr de vouloir retirer le livreur ${driverName} de la flotte ?`)) {
      return;
    }
    this.http.delete(`${this.state.apiUrl}/api/delivery/drivers/${driverId}`).subscribe({
      next: () => {
        this.state.showToast(`Livreur ${driverName} retiré de la flotte`);
        this.state.loadMerchantDeliveries();
      },
      error: () => {
        this.state.showToast('Erreur lors du retrait du livreur');
      },
    });
  }

  copyTrackingLink(orderId: string) {
    const url = `${this.state.apiUrl}/api/delivery/track/${orderId}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(
        () => this.state.showToast('📋 Lien de suivi copié dans le presse-papier !'),
        () => this.state.showToast(`Lien de suivi : ${url}`)
      );
    } else {
      this.state.showToast(`Lien de suivi : ${url}`);
    }
  }

  openPublicTracking(orderId: string) {
    window.open(`${this.state.apiUrl}/api/delivery/track/${orderId}`, '_blank');
  }

  returnToPlatform() {
    this.authService.stopImpersonation();
    this.router.navigate(['/platform']);
    this.state.showToast("Session d'impersonation terminée — Retour au cockpit Super Admin");
  }

  logout() {
    this.state.stopAutoRefresh();
    this.authService.logout();
    this.router.navigate(['/login']);
  }
}
