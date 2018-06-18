from app import app, db
from app.models import FeatureRequest, Client
from app.schemas import FeatureRequestSchema, ClientSchema
from flask import render_template, request, jsonify
from sqlalchemy import update

# This function works like a revolver
def rotate_list(items, up=True):
  if up:
    # Priority of current Increasing (in n to 1 direction)
    items.insert(0, items.pop(-1))
  else:
    # Priority of current Decreasing (in 1 to n direction)
    items.append(items.pop(0))
  return items

def reprioritize_feature_requests(client_id, cur_priority, new_priority):
  priorities = sorted([int(cur_priority), int(new_priority)])
  feature_requests = FeatureRequest.query.filter(
    FeatureRequest.client_id==client_id,
    FeatureRequest.priority.between(*priorities)
  ).order_by(
    FeatureRequest.priority.asc()
  )
  feature_requests_schema = FeatureRequestSchema(many=True)
  # The second param determines if the current item is being moved up or not.
  revolver = rotate_list(
    feature_requests_schema.dump(feature_requests).data,
    (int(cur_priority) > int(new_priority))
  )
  for index, item in enumerate(revolver):
    if item != None:
      revolver[index]["priority"] = (index + priorities[0])
      update = db.session.query(FeatureRequest).filter_by(id=item['id']).update({
        "priority": revolver[index]["priority"]
      })
      db.session.commit()
  # Add some error handling.
  return revolver

## Routes
## Reference: REST API Design Rulebook

## Page Related
@app.route('/')
def index():
  return render_template('index.html')

@app.route('/clients')
def clients():
  return render_template('clients.html')

@app.route('/feature-requests/<client_id>')
def feature_requests(client_id):
  return render_template('feature-requests.html')

## API Related
@app.route('/api/feature-requests')
def get_feature_requests():
  feature_requests = FeatureRequest.query.all()
  feature_requests_schema = FeatureRequestSchema(many=True)
  result = feature_requests_schema.dump(feature_requests).data
  return jsonify(feature_requests=result)

@app.route('/api/feature-requests/new', methods=['POST'])
def create_feature_request():
  # Grab the highest priority (for this client).
  initial_priority = FeatureRequest.nextPriorityByClient(request.json['client_id'])
  feature_request = FeatureRequest(
    title=request.json['title'],
    description=(request.json['description'] if 'description' in request.json.keys() else ""),
    priority=initial_priority,
    client_id=request.json['client_id']
  )
  db.session.add(feature_request)
  db.session.commit()
  id = feature_request.id

  # We'll return all records with adjusted priority.
  return jsonify(
    reprioritize_feature_requests(request.json['client_id'], initial_priority, request.json['priority'])
  )

@app.route('/api/feature-requests/prioritize', methods=['POST'])
def prioritize_feature_request():
  result = reprioritize_feature_requests(
    request.json['client_id'],
    request.json['cur_priority'],
    request.json['new_priority']
  )
  return jsonify(feature_requests=result);

@app.route('/api/feature-requests/delete/<feature_request_id>', methods=['DELETE'])
def delete_feature_request(feature_request_id):
  feature_request = FeatureRequest.query.filter(FeatureRequest.id==feature_request_id).first()
  print(feature_request)
  db.session.delete(feature_request)
  # Should re-prioritize...
  result = reprioritize_feature_requests(
    feature_request.client_id,
    feature_request.priority,
    (FeatureRequest.nextPriorityByClient(feature_request.client_id)-1)
  )
  return jsonify(success=result)

@app.route('/api/clients')
def get_clients():
  clients = Client.query.all()
  clients_schema = ClientSchema(many=True)
  result = clients_schema.dump(clients).data
  return jsonify(clients=result)

@app.route('/api/clients/new', methods=['POST'])
def create_client():
  client = Client(
    name=request.json['name'],
  )
  db.session.add(client)
  db.session.commit()
  id = client.id
  return jsonify({
    "name": request.json['name'],
    "id": id
  })
