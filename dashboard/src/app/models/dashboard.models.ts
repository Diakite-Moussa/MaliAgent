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

export interface ProductCategory {
  id: string;
  business_id: string;
  name: string;
  description?: string | null;
  product_count: number;
  created_at?: string | null;
}

export interface ProductVariant {
  id?: string;
  name: string;
  value: string;
  label?: string;
  price?: number | null;
  stock_quantity: number;
  sku?: string | null;
  image_url?: string | null;
}

export interface Product {
  id: string;
  business_id: string;
  name: string;
  category: string;
  category_id?: string | null;
  price: number;
  stock_quantity: number;
  low_stock_threshold?: number;
  is_low_stock: boolean;
  is_out_of_stock: boolean;
  image_url?: string | null;
  has_variants?: boolean;
  variants?: ProductVariant[];
}

export interface AgentConfiguration {
  agent_name: string;
  tone: 'chaleureux' | 'formel' | 'concis' | string;
  default_language: 'fr' | 'bm' | string;
  custom_rules: string | null;
  welcome_message: string | null;
  enabled: boolean;
}

export interface KnowledgeDocument {
  id: string;
  filename: string;
  document_type: string;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  error_message?: string | null;
  uploaded_by_user_id?: string | null;
  created_at?: string | null;
  file_path?: string | null;
}

export interface PaymentItem {
  id: string;
  order_id: string;
  transaction_reference: string;
  provider: string;
  status: string;
  amount: number;
  currency: string;
  customer_phone: string | null;
  checkout_url: string | null;
  paid_at: string | null;
  created_at: string;
}

export interface HandoffMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string | null;
}

export interface HandoffConversation {
  id: string;
  customer_id: string;
  customer_phone: string;
  customer_name: string | null;
  handoff_reason: string;
  status: string;
  updated_at: string | null;
  messages: HandoffMessage[];
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

export interface DriverSummary {
  driver_name: string;
  driver_phone: string | null;
  is_available: boolean;
  total_delivered_count: number;
  total_cash_collected: number;
  active_missions_count: number;
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
