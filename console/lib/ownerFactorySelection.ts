export type OwnerFactorySelection = {
  id: string;
  name: string;
  timezone: string;
};

export function selectOwnerFactory(
  factories: OwnerFactorySelection[],
  requestedFactoryId?: string,
) {
  if (factories.length === 0) return { kind: "none" as const };
  if (requestedFactoryId) {
    const factory = factories.find(
      (candidate) => candidate.id === requestedFactoryId,
    );
    return factory
      ? { kind: "ready" as const, factory }
      : { kind: "choose" as const, factories };
  }
  if (factories.length > 1) {
    return { kind: "choose" as const, factories };
  }
  return { kind: "ready" as const, factory: factories[0] };
}
