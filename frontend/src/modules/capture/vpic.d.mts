export interface VpicProfile {
  readonly vin: string;
  readonly make: string;
  readonly model: string;
  readonly modelYear: number;
  readonly bodyClass: string;
  readonly trim: string | null;
  readonly series: string | null;
  readonly driveType: string | null;
  readonly engineCylinders: number | null;
  readonly displacementL: number | null;
  readonly fuelType: string | null;
  readonly transmission: string | null;
  readonly plantCountry: string | null;
  readonly checkDigitStatus: 'MATCH' | 'MISMATCH_OVERRIDE';
  readonly curbWeightStatus: 'reported' | 'unavailable' | 'invalid';
  readonly curbWeightLb: number | null;
  readonly curbWeightKg: number | null;
}
interface VpicBase {
  readonly scope: 'parsed-vpic-format-not-source-authentication';
  readonly rawResult: Readonly<Record<string, unknown>> | null;
  readonly decodeErrorCode: string | null;
  readonly suggestedVin: string | null;
  readonly physicsReady: false;
  readonly massBoundsConfigured: false;
}
export interface VpicParsed extends VpicBase {
  readonly status: 'parsed';
  readonly reason: null;
  readonly profile: VpicProfile;
}
export interface VpicBlocked extends VpicBase {
  readonly status: 'blocked';
  readonly reason: 'INVALID_REQUEST_VIN' | 'INVALID_RESPONSE' | 'VIN_MISMATCH' | 'DECODE_STATUS_UNRESOLVED' | 'SUGGESTED_VIN_REQUIRES_REVIEW' | 'INCOMPLETE_PROFILE';
  readonly profile: null;
}
export function parseVpicResponse(requestedVin: unknown, payload: unknown, options?: {allowCheckDigitMismatch?: boolean}): VpicParsed | VpicBlocked;
