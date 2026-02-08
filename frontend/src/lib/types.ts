/**
 * TypeScript interfaces matching Python Pydantic models from cantena.models.
 * This is the contract between frontend and backend.
 */

// ── Enums (matching cantena.models.enums) ──────────────────────────────────

export enum BuildingType {
  APARTMENT_LOW_RISE = "apartment_low_rise",
  APARTMENT_MID_RISE = "apartment_mid_rise",
  APARTMENT_HIGH_RISE = "apartment_high_rise",
  OFFICE_LOW_RISE = "office_low_rise",
  OFFICE_MID_RISE = "office_mid_rise",
  OFFICE_HIGH_RISE = "office_high_rise",
  RETAIL = "retail",
  WAREHOUSE = "warehouse",
  SCHOOL_ELEMENTARY = "school_elementary",
  SCHOOL_HIGH = "school_high",
  HOSPITAL = "hospital",
  HOTEL = "hotel",
}

export enum StructuralSystem {
  WOOD_FRAME = "wood_frame",
  STEEL_FRAME = "steel_frame",
  CONCRETE_FRAME = "concrete_frame",
  MASONRY_BEARING = "masonry_bearing",
  PRECAST_CONCRETE = "precast_concrete",
}

export enum ExteriorWall {
  BRICK_VENEER = "brick_veneer",
  CURTAIN_WALL = "curtain_wall",
  METAL_PANEL = "metal_panel",
  PRECAST_PANEL = "precast_panel",
  STUCCO = "stucco",
  WOOD_SIDING = "wood_siding",
  EIFS = "eifs",
}

export enum MechanicalSystem {
  SPLIT_SYSTEM = "split_system",
  PACKAGED_ROOFTOP = "packaged_rooftop",
  CHILLED_WATER = "chilled_water",
  VAV = "vav",
  VRF = "vrf",
}

export enum ElectricalService {
  LIGHT = "light",
  STANDARD = "standard",
  HEAVY = "heavy",
}

export enum FireProtection {
  NONE = "none",
  SPRINKLER_WET = "sprinkler_wet",
  SPRINKLER_COMBINED = "sprinkler_combined",
}

export enum Confidence {
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
}

// ── Building input models (matching cantena.models.building) ───────────────

export interface Location {
  city: string;
  state: string;
  zip_code?: string | null;
}

export interface ComplexityScores {
  structural: number;
  mep: number;
  finishes: number;
  site: number;
}

export interface BuildingModel {
  building_type: BuildingType;
  building_use: string;
  gross_sf: number;
  stories: number;
  story_height_ft: number;
  structural_system: StructuralSystem;
  exterior_wall_system: ExteriorWall;
  mechanical_system?: MechanicalSystem | null;
  electrical_service?: ElectricalService | null;
  fire_protection?: FireProtection | null;
  location: Location;
  complexity_scores: ComplexityScores;
  special_conditions: string[];
  confidence: Record<string, Confidence>;
}

// ── Estimate output models (matching cantena.models.estimate) ──────────────

export interface CostRange {
  low: number;
  expected: number;
  high: number;
}

export interface DivisionCost {
  csi_division: string;
  division_name: string;
  cost: CostRange;
  percent_of_total: number;
  source: string;
}

export interface Assumption {
  parameter: string;
  assumed_value: string;
  reasoning: string;
  confidence: Confidence;
}

export interface BuildingSummary {
  building_type: string;
  gross_sf: number;
  stories: number;
  structural_system: string;
  exterior_wall: string;
  location: string;
}

export interface EstimateMetadata {
  engine_version: string;
  cost_data_version: string;
  estimation_method: string;
}

export interface CostEstimate {
  project_name: string;
  building_summary: BuildingSummary;
  total_cost: CostRange;
  cost_per_sf: CostRange;
  breakdown: DivisionCost[];
  assumptions: Assumption[];
  generated_at: string;
  location_factor: number;
  metadata: EstimateMetadata;
}

// ── API response (matching FastAPI /api/analyze response) ──────────────────

export interface AnalysisInfo {
  reasoning: string;
  warnings: string[];
}

export interface AnalyzeResponse {
  estimate: CostEstimate;
  building_model: BuildingModel;
  summary_dict: Record<string, string>;
  export_dict: Record<string, unknown>;
  analysis: AnalysisInfo;
  processing_time_seconds: number;
  pages_analyzed: number;
}
