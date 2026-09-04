class ContractError(RuntimeError):
    pass


class AuthorizationError(ContractError):
    pass


class CheckpointConflict(ContractError):
    pass
