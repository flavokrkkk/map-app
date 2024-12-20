from ast import Await
from botocore import session
from sqlalchemy import func, select, update
from sqlalchemy.orm import joinedload
from backend.database.models.geo_object import GeoObject, GeoObjectGeometry, GeoObjectProperty, GeoObjectStatus, GlobalLayer, GlobalLayerGeoObject
from backend.database.models.user import UserGeoObject
from backend.dto.geo_object import UpdateGeoObjectModel
from backend.repositories.base import SqlAlchemyRepository
from backend.utils.enums import StatusTypes


class GeoObjectRepository(SqlAlchemyRepository):
    model = GeoObject

    async def get_item(
        self, 
        object_id: int
    ) -> tuple[GeoObject, GeoObjectProperty, GeoObjectGeometry]:
        geo_object = (
            await self.session.execute(
                select(self.model).join(GeoObjectProperty)
                .options(joinedload(GeoObject.geometry))
                .options(joinedload(GeoObject.properties))
                .where(self.model.id == object_id)
            )
        ).scalar_one_or_none()
        property_object = (
            await self.session.execute(
                select(GeoObjectProperty)
                .where(GeoObjectProperty.geo_object_id == geo_object.id)
            )
        ).scalar_one_or_none()
        geometry = (
            await self.session.execute(
                select(GeoObjectGeometry)
                .where(GeoObjectGeometry.geo_object_id == geo_object.id)
            )
        ).scalar_one_or_none()
        return geo_object, property_object, geometry
    
    async def get_all_objects(self, global_layers: list[str], is_negative: bool):
        query = select(self.model)

        if global_layers:
            query = query.where(self.model.global_layers.any(GlobalLayer.name.in_(global_layers)))
        if is_negative is True:
            query = query.where(GeoObjectProperty.depth < 0).join(GeoObjectProperty)
        elif is_negative is False:
            query = query.where(GeoObjectProperty.depth > 0).join(GeoObjectProperty)

        all_objects = (await self.session.execute(query)).scalars().all()
        objects = [await self.get_item(object.id) for object in all_objects]
        return objects

    
    async def update_status(self, object_id: int, new_status: StatusTypes):
        await self.session.execute( 
            update(
                GeoObjectProperty
            ).where(
                GeoObjectProperty.geo_object_id == object_id
            ).values(
                status_id=new_status
            )
        )

    async def update_layers(self, object: GeoObject, global_layers: list[int]):
        object_layers = [
            GlobalLayerGeoObject(
                global_layer_id=global_layer_id,
                geo_object_id=object.id
            ) for global_layer_id in global_layers
        ]
        self.session.add_all(object_layers)
        await self.session.commit()

    async def update_property(self, object: GeoObject, update_data: dict):
        if not update_data:
            return
        
        await self.session.execute(
            update(
                GeoObjectProperty
            ).where(
                GeoObjectProperty.geo_object_id == object.id
            ).values(
                **update_data
            )
        )
        await self.session.commit()

    async def update_item(self, object: GeoObject, form: UpdateGeoObjectModel) -> GeoObject:
        if form.status:
            await self.update_status(object.id, form.status)
        if form.name:
            object.properties.name = form.name
        if form.global_layers:
            await self.update_layers(object, form.global_layers)
        update_property_data = {}
        if form.description:
            update_property_data["description"] = form.description
        if form.material:
            update_property_data["material"] = form.material
        
        await self.update_property(object, update_property_data)
        await self.session.commit()
        await self.session.refresh(object)
        return object
    
    async def get_user_saved_objects(self, user_id: int,):
        objects = (
            await self.session.execute(
                select(
                    UserGeoObject.geo_object_id,
                ).where(
                    UserGeoObject.user_id == user_id,
                )
            )
        ).scalars().all()
        return objects
    
    async def get_undergroud_count(self):
        underground_count = (
            await self.session.execute(
                select(
                    func.count(GeoObject.id)
                ).where(
                    GeoObjectProperty.depth < 0
                )
            )
        ).scalar_one_or_none()
        return underground_count
    
    async def get_aboveground_count(self):
        aboveground_count = (
            await self.session.execute(
                select(
                    func.count(GeoObject.id)
                ).where(
                    GeoObjectProperty.depth >= 0
                )
            )
        ).scalar_one_or_none()
        return aboveground_count
    
    async def get_avg_depth_aboveground(self):
        avg_depth = (
            await self.session.execute(
                select(
                    func.avg(GeoObjectProperty.depth)
                ).where(
                    GeoObjectProperty.depth >= 0
                )
            )
        ).scalar_one_or_none()
        return avg_depth
    
    async def get_avg_depth_underground(self):
        avg_depth = (
            await self.session.execute(
                select(
                    func.avg(GeoObjectProperty.depth)
                ).where(
                    GeoObjectProperty.depth < 0
                )
            )
        ).scalar_one_or_none()
        return avg_depth
    
    async def get_materials_count(self):
        materials_count = (
            await self.session.execute(
                (
                    select(
                        GeoObjectProperty.material,
                        func.count(GeoObjectProperty.id).label("count")
                    )
                    .group_by(GeoObjectProperty.material)
                    .order_by(func.count(GeoObjectProperty.id).desc())
                )
            )
        ).all()
        return materials_count
    
    async def get_active_status_count(self):
        active_status_count = (
            await self.session.execute(
                select(
                    func.count(GeoObjectProperty.status_id)
                ).join(GeoObjectStatus).where(
                    GeoObjectStatus.name == StatusTypes.ACTIVE.value
                )
            )
        ).scalar_one_or_none()
        return active_status_count
    
    async def get_inactive_status_count(self):
        inactive_status_count = (
            await self.session.execute(
                select(
                    func.count(GeoObjectProperty.status_id)
                ).join(GeoObjectStatus).where(
                    GeoObjectStatus.name == StatusTypes.INACTIVE.value
                )
            )
        ).scalar_one_or_none()
        return inactive_status_count