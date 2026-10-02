/**
 * Minimal Web Bluetooth API type declarations — TypeScript's standard
 * DOM lib doesn't include these (Web Bluetooth isn't part of the
 * standard DOM spec, only implemented by Chrome/Edge). Only what
 * bluetoothPrinter.ts actually uses is declared here, not the full API
 * surface.
 */

interface BluetoothRemoteGATTCharacteristic {
  writeValueWithoutResponse(value: BufferSource): Promise<void>;
  writeValue(value: BufferSource): Promise<void>;
}

interface BluetoothRemoteGATTService {
  getCharacteristic(uuid: string): Promise<BluetoothRemoteGATTCharacteristic>;
}

interface BluetoothRemoteGATTServer {
  connected: boolean;
  connect(): Promise<BluetoothRemoteGATTServer>;
  disconnect(): void;
  getPrimaryService(uuid: string): Promise<BluetoothRemoteGATTService>;
}

interface BluetoothDevice {
  gatt?: BluetoothRemoteGATTServer;
}

interface RequestDeviceOptions {
  filters?: { services?: string[] }[];
  optionalServices?: string[];
}

interface Bluetooth {
  requestDevice(options: RequestDeviceOptions): Promise<BluetoothDevice>;
}

interface Navigator {
  readonly bluetooth?: Bluetooth;
}
