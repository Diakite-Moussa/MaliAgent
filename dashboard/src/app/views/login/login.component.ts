import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../auth.service';
import { DashboardStateService } from '../../services/dashboard-state.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="login-view-container">
      <div class="login-glass-card">
        <div class="login-brand">
          <div class="login-logo">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              <circle cx="9" cy="10" r="1"></circle>
              <circle cx="15" cy="10" r="1"></circle>
            </svg>
          </div>
          <h1 class="login-title">MaliAgent</h1>
          <p class="login-subtitle">Portail commerçant & agent WhatsApp automatisé</p>
        </div>

        @if (loginError()) {
          <div class="login-error-badge">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <span>{{ loginError() }}</span>
          </div>
        }

        <form class="login-form" (submit)="submitLogin(); $event.preventDefault()">
          <div class="form-group">
            <label for="login-email">Adresse Email</label>
            <div class="input-container">
              <svg class="input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
              <input 
                id="login-email" 
                type="email" 
                [ngModel]="loginEmail()" 
                (ngModelChange)="loginEmail.set($event)" 
                name="email" 
                placeholder="admin@maliagent.ml" 
                required 
                autocomplete="username" />
            </div>
          </div>

          <div class="form-group">
            <label for="login-password">Mot de passe</label>
            <div class="input-container">
              <svg class="input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
              <input 
                id="login-password" 
                type="password" 
                [ngModel]="loginPassword()" 
                (ngModelChange)="loginPassword.set($event)" 
                name="password" 
                placeholder="••••••••" 
                required 
                autocomplete="current-password" />
            </div>
          </div>

          <button type="submit" class="btn-login" [disabled]="isLoggingIn()">
            @if (isLoggingIn()) {
              <div class="spinner-inline"></div>
              <span>Connexion en cours...</span>
            } @else {
              <span>Se connecter</span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
            }
          </button>
        </form>

        <div class="login-footer-info">
          <div class="security-chip">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
            <span>Session sécurisée par JWT & isolation multi-tenant</span>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class LoginComponent {
  private authService = inject(AuthService);
  private state = inject(DashboardStateService);
  private router = inject(Router);

  loginEmail = signal<string>('admin@maliagent.ml');
  loginPassword = signal<string>('');
  loginError = signal<string | null>(null);
  isLoggingIn = signal<boolean>(false);

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
        this.state.showToast(`Bienvenue, ${session.email} !`);

        if (this.authService.isSuperAdmin()) {
          this.state.viewMode.set('platform');
          this.state.loadPlatformAll();
          this.router.navigate(['/platform']);
        } else if (this.authService.isDriver()) {
          this.state.viewMode.set('driver');
          this.state.loadDriverMissions();
          this.router.navigate(['/driver']);
        } else {
          this.state.viewMode.set('merchant');
          this.state.refreshMerchantAll();
          this.router.navigate(['/merchant']);
        }
        this.state.startAutoRefresh();
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
}
