import { Injectable, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

export interface UserSession {
  access_token: string;
  token_type: string;
  business_id: string | null;
  email: string;
  role: string;
}

const STORAGE_KEY = 'maliagent_auth_session';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private http = inject(HttpClient);
  readonly apiUrl = 'http://localhost:8000';

  // État réactif de l'utilisateur connecté
  readonly currentUser = signal<UserSession | null>(this.loadSessionFromStorage());

  // Signal calculé d'authentification
  readonly isAuthenticated = computed(() => !!this.currentUser());

  // Signal vérifiant si l'utilisateur est le Super Admin de la plateforme
  readonly isSuperAdmin = computed(() => this.currentUser()?.role === 'super_admin');

  // Signal vérifiant si l'utilisateur est un Livreur
  readonly isDriver = computed(() => this.currentUser()?.role === 'livreur');

  private loadSessionFromStorage(): UserSession | null {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw) as UserSession;
    } catch {
      return null;
    }
  }

  // État d'impersonation (inspection d'une boutique avec token temporaire)
  readonly impersonationSession = signal<{
    originalSession: UserSession;
    businessId: string;
    businessName: string;
  } | null>(null);

  readonly isImpersonating = computed(() => !!this.impersonationSession());

  startImpersonation(tempToken: string, businessId: string, businessName: string): void {
    const current = this.currentUser();
    if (!current) return;

    this.impersonationSession.set({
      originalSession: current,
      businessId,
      businessName,
    });

    const tempSession: UserSession = {
      ...current,
      access_token: tempToken,
      business_id: businessId,
    };
    this.saveSession(tempSession);
  }

  stopImpersonation(): void {
    const imp = this.impersonationSession();
    if (imp) {
      this.saveSession(imp.originalSession);
      this.impersonationSession.set(null);
    }
  }

  login(email: string, password: string): Observable<UserSession> {
    return this.http
      .post<UserSession>(`${this.apiUrl}/api/auth/login`, {
        email: email.trim().toLowerCase(),
        password,
      })
      .pipe(
        tap((session) => {
          this.impersonationSession.set(null);
          this.saveSession(session);
        })
      );
  }

  logout(): void {
    localStorage.removeItem(STORAGE_KEY);
    this.impersonationSession.set(null);
    this.currentUser.set(null);
  }

  getToken(): string | null {
    return this.currentUser()?.access_token ?? null;
  }

  private saveSession(session: UserSession): void {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    this.currentUser.set(session);
  }
}
