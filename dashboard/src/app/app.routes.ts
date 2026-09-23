import { Routes } from '@angular/router';
import { authGuard, guestGuard, superAdminGuard, driverGuard } from './guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./views/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'merchant',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./views/merchant/merchant-view.component').then((m) => m.MerchantViewComponent),
  },
  {
    path: 'platform',
    canActivate: [superAdminGuard],
    loadComponent: () =>
      import('./views/platform/platform-view.component').then((m) => m.PlatformViewComponent),
  },
  {
    path: 'driver',
    canActivate: [driverGuard],
    loadComponent: () =>
      import('./views/driver/driver-view.component').then((m) => m.DriverViewComponent),
  },
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'merchant',
  },
  {
    path: '**',
    redirectTo: 'merchant',
  },
];
