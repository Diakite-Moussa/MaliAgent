import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from './auth.service';
import { catchError, throwError } from 'rxjs';

/**
 * Intercepteur HTTP gérant l'architecture d'authentification hybride :
 * 1. withCredentials = true : transmet automatiquement le cookie HttpOnly 'access_token' sécurisé.
 * 2. Authorization Bearer : injecté pour les sessions d'impersonation (Super Admin) ou API clients.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const token = authService.getToken();

  // On active systématiquement withCredentials pour envoyer les cookies de session HttpOnly
  const headers: Record<string, string> = {};
  if (token && !req.url.includes('/api/auth/login')) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const authReq = req.clone({
    withCredentials: true,
    setHeaders: headers,
  });

  return next(authReq).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !req.url.includes('/api/auth/login')) {
        // Session expirée ou invalide : déconnexion automatique
        authService.logout();
      }
      return throwError(() => error);
    })
  );
};
