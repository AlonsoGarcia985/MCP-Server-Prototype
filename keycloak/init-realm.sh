#!/bin/sh
echo "Esperando que Keycloak esté listo..."
until curl -sf http://keycloak:8080/realms/master > /dev/null 2>&1; do
  echo "Esperando..."
  sleep 5
done

echo "Obteniendo token de admin..."
TOKEN=$(curl -s -X POST http://keycloak:8080/realms/master/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin&grant_type=password&client_id=admin-cli" \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

echo "Verificando si el realm ya existe..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  http://keycloak:8080/admin/realms/mcp-proto)

if [ "$STATUS" = "200" ]; then
  echo "El realm mcp-proto ya existe, omitiendo creación."
else
  echo "Creando realm mcp-proto..."
  curl -s -X POST http://keycloak:8080/admin/realms \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d @/realm-export.json
  echo "Realm creado exitosamente."
fi
