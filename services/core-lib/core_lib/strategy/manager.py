"""Coordinate Adaptee creation, configuration, registry access, and lifecycle."""

from collections.abc import Mapping, Sequence

from core_lib.money_management import (
    MoneyManagementBase,
    MoneyManagementFactory,
    reconcile_money_management_availability,
)
from core_lib.ports import StrategyRegistry

from .base import StrategyAdapter, StrategyDecisionContract, StrategyRuntime
from .config import StrategyConfig
from .factory import AdapterFactory
from .reconciliation import (
    StrategyReconciliation,
    catalog_declaration_mismatch,
    reconcile_strategy_registries,
)
from .registry import InProcessStrategyRegistry


class AdapterManager:
    """Orchestrate schema lookup, config resolution, creation, and lifecycle."""

    def __init__(
        self,
        catalog_registry: StrategyRegistry,
        adapter_registry: InProcessStrategyRegistry,
        *,
        money_management_policies: Mapping[str, type[MoneyManagementBase]],
        money_management_registrations: Sequence[Mapping[str, object]] | None = None,
        config: type[StrategyConfig] = StrategyConfig,
        factory: type[AdapterFactory] = AdapterFactory,
    ) -> None:
        self._catalog_registry = catalog_registry
        self._adapter_registry = adapter_registry
        self._config = config
        self._factory = factory
        # Passed in rather than imported, because the deployed policies live outside
        # core_lib and core_lib must not reach into a service to find them.
        self._money_management_policies = money_management_policies
        self._money_management_registrations = money_management_registrations
        self._instances: dict[str, StrategyAdapter] = {}
        self._active: set[str] = set()

    def create(
        self,
        strategy_id: str,
        raw_config: Mapping[str, object],
    ) -> StrategyAdapter:
        """Follow catalog lookup → schema declaration → resolve → construction."""
        catalog_entry = self._catalog_registry.get(strategy_id)
        self._validate_catalog_entry(strategy_id, catalog_entry)
        adaptee_class = self._adapter_registry.get(strategy_id)
        self._validate_class_identity(adaptee_class, catalog_entry)
        self._validate_declared_history(adaptee_class, catalog_entry)

        schema = adaptee_class.get_parameter_schema()
        resolved = self._config.resolve(schema, raw_config)
        if resolved.strategy_id != strategy_id:
            raise ValueError(
                "create strategy_id does not match raw_config.strategy_id: "
                f"{strategy_id!r} != {resolved.strategy_id!r}"
            )
        instance = self._factory.create(adaptee_class, resolved)
        self._instances[strategy_id] = instance
        return instance

    def create_runtime(
        self,
        strategy_id: str,
        raw_config: Mapping[str, object],
        money_management_config: Mapping[str, object],
    ) -> StrategyRuntime:
        """Compose one strategy with a validated policy it explicitly supports."""
        strategy = self.create(strategy_id, raw_config)
        metadata = strategy.get_metadata()
        support = metadata.money_management
        if not support.supported:
            return StrategyRuntime(strategy=strategy, money_management=None)
        if metadata.decision_contract is StrategyDecisionContract.TRADING_SIGNAL:
            raise ValueError(
                f"strategy {strategy_id!r} declares TradingSignal and cannot attach "
                "money management"
            )
        mode = money_management_config.get("mode")
        if isinstance(mode, str):
            availability = next(
                (
                    item
                    for item in reconcile_money_management_availability(
                        self._money_management_registrations,
                        self._money_management_policies,
                    )
                    if item.mode == mode
                ),
                None,
            )
            if availability is not None and not availability.runnable:
                reason = availability.reason
                raise ValueError(
                    f"money-management mode {mode!r} is not runnable: "
                    f"{None if reason is None else reason.value}"
                )
        policy = MoneyManagementFactory.create(
            money_management_config, self._money_management_policies
        )
        if policy.id not in support.supported:
            raise ValueError(
                f"strategy {strategy_id!r} does not support money-management mode {policy.id!r}"
            )
        requires_signal_exit = getattr(policy, "requires_signal_exit", None)
        if not isinstance(requires_signal_exit, bool):
            # Reading a missing declaration as false pairs a policy that never
            # plans an exit with a strategy that cannot emit one, and the trade
            # then has nothing to close it.
            raise ValueError(f"{policy.id} money management does not declare requires_signal_exit")
        if requires_signal_exit and not support.supports_signal_exit:
            raise ValueError(f"{policy.id} money management requires strategy signal exits")
        return StrategyRuntime(strategy=strategy, money_management=policy)

    @staticmethod
    def _validate_catalog_entry(
        strategy_id: str,
        catalog_entry: Mapping[str, object],
    ) -> None:
        catalog_strategy_id = catalog_entry.get("strategy_id")
        if catalog_strategy_id is not None and catalog_strategy_id != strategy_id:
            raise ValueError("external catalog returned a mismatched strategy_id")
        if catalog_entry.get("is_active") is False:
            raise ValueError(f"strategy is inactive in the external catalog: {strategy_id}")
        if catalog_entry.get("is_deprecated") is True:
            raise ValueError(f"strategy is deprecated in the external catalog: {strategy_id}")

    @staticmethod
    def _validate_class_identity(
        adaptee_class: type[StrategyAdapter],
        catalog_entry: Mapping[str, object],
    ) -> None:
        class_name = catalog_entry.get("class_name")
        if class_name is not None and class_name != adaptee_class.__name__:
            raise ValueError("external catalog class_name does not match in-process Adaptee")
        module_path = catalog_entry.get("module_path")
        if module_path is not None and module_path != adaptee_class.__module__:
            raise ValueError("external catalog module_path does not match in-process Adaptee")

    @staticmethod
    def _validate_declared_history(
        adaptee_class: type[StrategyAdapter],
        catalog_entry: Mapping[str, object],
    ) -> None:
        """Refuse to run when the registration disagrees with the Adaptee it names.

        How much history a run reads is derived from the Adaptee's declared indicators
        and minimum history. The same facts are registered in the catalog so operators
        and the console can see them without importing code. Nothing reconciled the
        two, so a registration could drift from the class it names and quietly describe
        a run that never happens. A disagreement is refused here rather than resolved,
        because either side could be the stale one.
        """
        metadata = adaptee_class.get_metadata()
        mismatch = catalog_declaration_mismatch(catalog_entry, metadata)
        if mismatch is not None:
            raise ValueError(mismatch)

    def activate(self, strategy_id: str) -> None:
        """Activate a created Adaptee instance."""
        if strategy_id not in self._instances:
            raise KeyError(f"strategy instance has not been created: {strategy_id}")
        self._active.add(strategy_id)

    def deactivate(self, strategy_id: str) -> None:
        """Deactivate a created Adaptee instance."""
        if strategy_id not in self._instances:
            raise KeyError(f"strategy instance has not been created: {strategy_id}")
        self._active.discard(strategy_id)

    def is_active(self, strategy_id: str) -> bool:
        """Return the local lifecycle state of a created Adaptee."""
        return strategy_id in self._active

    def list_registered(self) -> list[str]:
        """Return stable ids from the injected external catalog."""
        strategy_ids: list[str] = []
        for entry in self._catalog_registry.list():
            strategy_id = entry.get("strategy_id")
            if not isinstance(strategy_id, str) or not strategy_id:
                raise ValueError("external catalog row has no valid strategy_id")
            strategy_ids.append(strategy_id)
        return sorted(strategy_ids)

    def reconcile_catalog(self) -> tuple[StrategyReconciliation, ...]:
        """Return whole-catalog findings without changing the single-create path."""
        return reconcile_strategy_registries(
            self._catalog_registry,
            self._adapter_registry,
        )

    def register(self, strategy_id: str, meta: dict[str, object]) -> None:
        """Delegate external catalog registration after confirming the plugin exists."""
        self._adapter_registry.get(strategy_id)
        self._catalog_registry.register(strategy_id, meta)
