import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { DashboardStateService } from './services/dashboard-state.service';
import { AuthService } from './auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet],
  templateUrl: './app.html',
})
export class App implements OnInit {
  readonly state = inject(DashboardStateService);
  readonly authService = inject(AuthService);

  ngOnInit() {
    if (this.authService.isAuthenticated()) {
      this.state.startAutoRefresh();
    }
  }
}
