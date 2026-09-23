import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { AuthService } from '../../auth.service';
import { DashboardStateService } from '../../services/dashboard-state.service';
import { DriverMission } from '../../models/dashboard.models';

@Component({
  selector: 'app-driver-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './driver-view.component.html',
})
export class DriverViewComponent implements OnInit {
  readonly state = inject(DashboardStateService);
  readonly authService = inject(AuthService);
  private http = inject(HttpClient);
  private router = inject(Router);

  driverTab = signal<'active' | 'history'>('active');
  selectedMissionForOtp = signal<DriverMission | null>(null);
  otpInput = signal<string>('');
  isVerifyingOtp = signal<boolean>(false);
  otpError = signal<string | null>(null);

  readonly driverMissions = this.state.driverMissions;
  readonly activeDriverMissions = this.state.activeDriverMissions;
  readonly completedDriverMissions = this.state.completedDriverMissions;
  readonly driverSummary = this.state.driverSummary;
  readonly backendConnected = this.state.backendConnected;

  isTogglingAvailability = signal<boolean>(false);

  ngOnInit() {
    this.loadDriverMissions();
  }

  loadDriverMissions() {
    this.state.loadDriverMissions();
  }

  toggleAvailability() {
    const current = this.driverSummary()?.is_available ?? true;
    const target = !current;
    this.isTogglingAvailability.set(true);
    this.http.patch(`${this.state.apiUrl}/api/delivery/driver/availability`, { is_available: target }).subscribe({
      next: () => {
        this.isTogglingAvailability.set(false);
        this.state.showToast(`Statut mis à jour : ${target ? '🟢 En service' : '⏸ En pause'}`);
        this.state.loadDriverSummary();
      },
      error: () => {
        this.isTogglingAvailability.set(false);
        this.state.showToast('Erreur lors du changement de disponibilité');
      },
    });
  }

  formatFcfa(val: number | null | undefined): string {
    if (val === null || val === undefined) return '0 FCFA';
    return Number(val).toLocaleString('fr-FR') + ' FCFA';
  }

  pickupMission(m: DriverMission) {
    this.http.post(`${this.state.apiUrl}/api/delivery/driver/missions/${m.id}/pickup`, {}).subscribe({
      next: () => {
        this.state.showToast('Colis récupéré en boutique !');
        this.loadDriverMissions();
      },
      error: () => {
        this.state.showToast('Erreur lors de la récupération du colis');
      },
    });
  }

  startRouteMission(m: DriverMission) {
    this.http.post(`${this.state.apiUrl}/api/delivery/driver/missions/${m.id}/start-route`, {}).subscribe({
      next: () => {
        this.state.showToast('En route vers le client !');
        this.loadDriverMissions();
      },
      error: () => {
        this.state.showToast('Erreur lors du départ en route');
      },
    });
  }

  updateGpsLocation(m: DriverMission) {
    if (!navigator.geolocation) {
      this.state.showToast("La géolocalisation n'est pas supportée par votre navigateur");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const payload = { latitude: pos.coords.latitude, longitude: pos.coords.longitude };
        this.http.post(`${this.state.apiUrl}/api/delivery/driver/missions/${m.id}/location`, payload).subscribe({
          next: () => {
            this.state.showToast('Position GPS actualisée avec succès');
            this.loadDriverMissions();
          },
          error: () => {
            this.state.showToast("Erreur lors de l'actualisation GPS");
          },
        });
      },
      () => {
        this.state.showToast('Impossible de récupérer la position GPS (activez le GPS)');
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
      .post(`${this.state.apiUrl}/api/delivery/driver/missions/${mission.id}/verify-otp`, { otp_code: code })
      .subscribe({
        next: () => {
          this.isVerifyingOtp.set(false);
          this.state.showToast('🎉 Livraison validée avec succès !');
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

  logout() {
    this.state.stopAutoRefresh();
    this.authService.logout();
    this.router.navigate(['/login']);
  }
}
