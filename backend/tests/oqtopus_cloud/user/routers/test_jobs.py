# from api.common.models.device import (
#     Device,
# )
# from api.common.models.task import (
#     Task,
# )
# from api.user.lambda_function import app
# from api.user.schemas.tasks import (
#     PostTaskRequest,
# )
# from fastapi.testclient import (
#     TestClient,
# )

# client = TestClient(app)


# def test_get_task_404(
#     test_db,
# ):
#     """_summary_

#     Args:
#             test_db (_type_): _description_
#     """
#     print(test_db)  # => 1
#     response = client.get("/tasks/e8a60c14-8838-46c9-816a-30191d6ab517")
#     assert response.status_code == 404
#     assert response.json() == {"detail": "task not found with the given id"}


# def test_get_task_200(
#     test_db,
# ):
#     """_summary_

#     Args:
#             test_db (_type_): _description_
#     """
#     device = Device(
#         id="1",
#         device_type="simulator",
#         status="AVAILABLE",
#         n_qubits=1,
#         n_nodes=1,
#         basis_gates="basis_gates",
#         instructions="instructions",
#         description="description",
#     )
#     task = Task(
#         id=b"\xe8\xa6\x0c\x14\x888F\xc9\x81j0\x19\x1dj\xb5\x17",
#         owner="owner",
#         code="code",
#         action="sampling",
#         device="1",
#         n_qubits=1,
#         n_nodes=1,
#         skip_transpilation=False,
#         seed_transpilation=1,
#         seed_simulation=1,
#         ro_error_mitigation="none",
#         n_per_node=1,
#         created_at="2021-01-01 00:00:00",
#     )
#     test_db.add(device)
#     test_db.add(task)
#     test_db.flush()
#     test_db.commit()
#     response = client.get("/tasks/e8a60c14-8838-46c9-816a-30191d6ab517")
#     assert response.status_code == 200
#     assert response.json() == {
#         "taskId": "e8a60c14-8838-46c9-816a-30191d6ab517",
#         "code": "code",
#         "device": "1",
#         "nQubits": 1,
#         "qubitAllocation": None,
#         "nNodes": 1,
#         "skipTranspilation": False,
#         "simulationOpt": None,
#         "seedTranspilation": 1,
#         "seedSimulation": 1,
#         "roErrorMitigation": "none",
#         "nPerNode": 1,
#     }


# def test_post_task_201(
#     test_db,
# ):
#     """_summary_

#     Args:
#             test_db (_type_): _description_
#     """
#     device = Device(
#         id="1",
#         device_type="simulator",
#         status="AVAILABLE",
#         n_qubits=1,
#         n_nodes=1,
#         basis_gates="basis_gates",
#         instructions="instructions",
#         description="description",
#     )

#     test_db.add(device)
#     test_db.flush()
#     test_db.commit()
#     body = PostTaskRequest(
#         name=None,
#         code="code",
#         device="1",
#         nQubits=1,
#         nNodes=1,
#         nShots=1,
#         qubitAllocation=None,
#         skipTranspilation=False,
#         seedTranspilation=1,
#         seedSimulation=1,
#         roErrorMitigation=None,
#         nPerNode=1,
#         simulationOpt=None,
#         note=None,
#     )
#     response = client.post("/tasks", content=body.model_dump_json())
#     assert response.status_code == 201
