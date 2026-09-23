import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { AuthService } from '../../auth.service';
import { DashboardStateService } from '../../services/dashboard-state.service';
import { PlatformBusiness, PlatformUser, PlatformAuditLog } from '../../models/dashboard.models';

@Component({
  selector: 'app-platform-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './platform-view.component.html',
})
export class PlatformViewComponent implements OnInit {
  readonly state = inject(DashboardStateService);
  readonly authService = inject(AuthService);
  private http = inject(HttpClient);
  private router = inject(Router);

  // Navigation Super Admin
  activePlatformTab = signal<'overview' | 'businesses' | 'users' | 'health' | 'audit'>('overview');
  auditFilterAction = signal<string>('');

  // Modales
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

  // Signaux proxy vers le state global pour compatibilité template
  readonly platformStats = this.state.platformStats;
  readonly platformBusinesses = this.state.platformBusinesses;
  readonly platformUsers = this.state.platformUsers;
  readonly platformHealth = this.state.platformHealth;
  readonly platformAuditLogs = this.state.platformAuditLogs;
  readonly backendConnected = this.state.backendConnected;

  ngOnInit() {
    this.loadPlatformAll();
  }

  loadPlatformAll() {
    this.state.loadPlatformAll();
  }

  formatFcfa(val: number | null | undefined): string {
    if (val === null || val === undefined) return '0 FCFA';
    return Number(val).toLocaleString('fr-FR') + ' FCFA';
  }

  loadPlatformHealth() {
    this.state.loadPlatformHealth();
  }

  loadPlatformAuditLogs(actionFilter?: string) {
    this.state.loadPlatformAuditLogs(actionFilter);
  }

  submitNewBusiness() {
    if (!this.newBusiness.name || !this.newBusiness.whatsapp_phone_number) {
      this.state.showToast('Veuillez renseigner le nom et le numéro WhatsApp');
      return;
    }
    this.http.post(`${this.state.apiUrl}/api/platform/businesses`, this.newBusiness).subscribe({
      next: (created: any) => {
        this.state.showToast(`Boutique ${created.name} créée avec succès !`);
        this.showCreateBusinessModal.set(false);
        this.newBusiness = { name: '', whatsapp_phone_number: '', currency: 'XOF' };
        this.state.loadPlatformBusinesses();
        this.state.loadPlatformStats();
      },
      error: (err) => {
        this.state.showToast(err.error?.detail || 'Erreur lors de la création de la boutique');
      },
    });
  }

  toggleBusinessStatus(biz: PlatformBusiness) {
    const newStatus = !biz.is_active;
    this.http
      .patch(`${this.state.apiUrl}/api/platform/businesses/${biz.id}`, { is_active: newStatus })
      .subscribe({
        next: () => {
          this.state.showToast(
            `Boutique ${biz.name} ${newStatus ? 'réactivée' : 'suspendue'} avec succès`
          );
          this.state.loadPlatformBusinesses();
          this.state.loadPlatformStats();
        },
        error: () => {
          this.state.showToast('Erreur lors du changement de statut');
        },
      });
  }

  submitNewUser() {
    if (!this.newUser.email || !this.newUser.password || !this.newUser.first_name) {
      this.state.showToast('Veuillez remplir les champs obligatoires');
      return;
    }
    const payload: any = { ...this.newUser };
    if (payload.role === 'super_admin') {
      delete payload.business_id;
    }
    this.http.post(`${this.state.apiUrl}/api/platform/users`, payload).subscribe({
      next: (created: any) => {
        this.state.showToast(`Utilisateur ${created.email} créé avec succès !`);
        this.showCreateUserModal.set(false);
        this.newUser = {
          email: '',
          password: '',
          first_name: '',
          last_name: '',
          role: 'admin',
          business_id: '',
        };
        this.state.loadPlatformUsers();
        this.state.loadPlatformStats();
      },
      error: (err) => {
        this.state.showToast(err.error?.detail || "Erreur lors de la création de l'utilisateur");
      },
    });
  }

  toggleUserStatus(u: PlatformUser) {
    const newStatus = !u.is_active;
    this.http
      .patch(`${this.state.apiUrl}/api/platform/users/${u.id}`, { is_active: newStatus })
      .subscribe({
        next: () => {
          this.state.showToast(
            `Compte ${u.email} ${newStatus ? 'activé' : 'désactivé'} avec succès`
          );
          this.state.loadPlatformUsers();
        },
        error: (err) => {
          this.state.showToast(err.error?.detail || 'Erreur lors de la mise à jour');
        },
      });
  }

  inspectBusiness(biz: PlatformBusiness) {
    this.http
      .post<{
        impersonation_token: string;
        business_id: string;
        business_name: string;
        expires_in_minutes: number;
      }>(`${this.state.apiUrl}/api/platform/impersonate/${biz.id}`, {})
      .subscribe({
        next: (res) => {
          this.authService.startImpersonation(
            res.impersonation_token,
            res.business_id,
            res.business_name
          );
          this.state.business.set({
            id: biz.id,
            name: biz.name,
            currency: biz.currency,
            whatsapp_phone_number: biz.whatsapp_phone_number,
          });
          this.state.viewMode.set('merchant');
          this.state.refreshMerchantAll();
          this.router.navigate(['/merchant']);
          this.state.showToast(
            `Session d'inspection active (15 min) : ${biz.name} — Actions tracées dans l'audit.`
          );
        },
        error: (err) => {
          this.state.showToast(err.error?.detail || "Impossible d'inspecter cette boutique");
        },
      });
  }

  logout() {
    this.state.stopAutoRefresh();
    this.authService.logout();
    this.router.navigate(['/login']);
  }
}
