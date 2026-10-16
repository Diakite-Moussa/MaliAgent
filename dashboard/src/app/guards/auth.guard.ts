import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../auth.service';

export const authGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(['/login']);
};

export const guestGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.isAuthenticated()) {
    return true;
  }

  if (authService.isSuperAdmin()) {
    return router.createUrlTree(['/platform']);
  }
  if (authService.isDriver()) {
    return router.createUrlTree(['/driver']);
  }
  return router.createUrlTree(['/merchant']);
};

export const superAdminGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated() && authService.isSuperAdmin()) {
    return true;
  }

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/login']);
  }

  return router.createUrlTree(['/merchant']);
};

export const driverGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated() && authService.isDriver()) {
    return true;
  }

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/login']);
  }

  return router.createUrlTree(['/merchant']);
};
